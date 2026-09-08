"""
Compute BINARY classification targets for UP/DOWN movement prediction.

TARGETS: y_class_1d, y_class_5d, y_class_20d
- Binary classification: 1 (UP), -1 (DOWN)
- Uses raw forward returns (positive = UP, non-positive = DOWN)

CRITICAL: All targets use FORWARD-SHIFTED data (no leakage).
- future_<h> = close.shift(-h) uses the close h trading days ahead.

Rows near the end of the series have no future close yet; their labels and
outcome prices stay NULL so today's row can still be written for inference.
"""

import numpy as np
import pandas as pd

# Trading-day horizons the whole system is built around. Adding one here
# propagates to labels, outcome prices, training and inference.
HORIZONS = (1, 5, 20)


def _binary_class(fwd_ret: pd.Series) -> pd.Series:
    """1 where the forward return is positive, -1 where it is not, None where unknown."""
    cls = pd.Series(-1, index=fwd_ret.index, dtype=object)
    cls[fwd_ret > 0] = 1
    return cls.where(fwd_ret.notna(), None)


def compute_labels(
    close: pd.Series,
    vol_20: pd.Series,          # 20-day realized volatility, for vol-scaling
    y_thresh: float = 0.002,
    keep_incomplete: bool = True,
) -> pd.DataFrame:
    """
    Compute binary UP/DOWN targets for every horizon in HORIZONS.

    Args:
        close: Close prices (chronological)
        vol_20: 20-day rolling volatility used to scale returns
        y_thresh: Threshold for the legacy y_thresh column
        keep_incomplete: Keep trailing rows that have no future close yet
                         (their labels are NULL rather than dropped)

    Returns:
        DataFrame indexed like `close` with outcome prices, classification
        targets and diagnostic regression targets per horizon.
    """
    out = {}
    vol = vol_20 + 1e-9  # avoid division by zero

    for h in HORIZONS:
        future = close.shift(-h)
        raw = np.log(future / close)

        out[f"outcome_price_{h}d"] = future
        out[f"y_{h}d_raw"] = raw
        out[f"y_{h}d_vol"] = raw / vol
        out[f"y_{h}d_clipped"] = raw.clip(-3 * raw.std(), 3 * raw.std())
        out[f"y_{h}d_vol_clip"] = (raw / vol).clip(-3.0, 3.0)
        out[f"y_class_{h}d"] = _binary_class(raw)

        # Legacy 0/1 columns kept so existing DB columns keep filling.
        if h in (1, 5):
            out[f"y_{h}d"] = (future > close).astype("Int64").where(future.notna(), None)

    # Default regression target for anything that asks for just one.
    out["primary_target"] = out["y_1d_vol_clip"]

    # Legacy threshold-crossing target.
    ret_1d = close.shift(-1) / close - 1.0
    out["y_thresh"] = (ret_1d > y_thresh).astype("Int64").where(ret_1d.notna(), None)

    labels = pd.DataFrame(out)

    if not keep_incomplete:
        # Drop the tail whose longest-horizon future close is unknown.
        drop = max(HORIZONS)
        labels = labels.iloc[:-drop] if len(labels) > drop else labels.iloc[0:0]

    return labels
