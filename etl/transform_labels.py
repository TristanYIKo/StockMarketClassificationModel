"""
Compute BINARY classification targets for UP/DOWN movement prediction.

PRIMARY TARGET: y_class_1d
- Binary classification: 1 (UP), -1 (DOWN)
- Uses raw returns (positive = UP, negative = DOWN)
- Simple, direct prediction of market direction

CRITICAL: All targets use FORWARD-SHIFTED data (no leakage).
- future_1d = close.shift(-1) uses NEXT day's close
"""

import numpy as np
import pandas as pd


def compute_labels(
    close: pd.Series, 
    vol_20: pd.Series,  # 20-day realized volatility for scaling
    y_thresh: float = 0.002
) -> pd.DataFrame:
    """
    Compute BINARY classification target: UP vs DOWN.
    
    PRIMARY TARGET: y_class_1d
    - 1 (UP): future_1d > close (price went up)
    - -1 (DOWN): future_1d <= close (price went down or flat)
    
    Args:
        close: Close prices (chronological)
        vol_20: 20-day rolling volatility (kept for diagnostic purposes)
        y_thresh: Legacy parameter, kept for backwards compatibility
    
    Returns:
        DataFrame with y_class_1d and supporting diagnostic columns
    """
    # Forward-shifted closes (FUTURE data, no leakage)
    future_1d = close.shift(-1)
    future_5d = close.shift(-5)
    
    # Raw log returns (regression targets)
    y_1d_raw = np.log(future_1d / close)
    y_5d_raw = np.log(future_5d / close)
    
    # Volatility-scaled returns (heteroskedasticity adjustment)
    # Divide by realized vol to stabilize variance across time
    y_1d_vol = y_1d_raw / (vol_20 + 1e-9)  # avoid division by zero
    y_5d_vol = y_5d_raw / (vol_20 + 1e-9)
    
    # Clipped returns (robustness to outliers)
    # Clip to ±3 standard deviations of raw returns
    std_1d = y_1d_raw.std()
    std_5d = y_5d_raw.std()
    y_1d_clipped = y_1d_raw.clip(-3 * std_1d, 3 * std_1d)
    y_5d_clipped = y_5d_raw.clip(-3 * std_5d, 3 * std_5d)
    
    # PRIMARY TARGETS: Volatility-scaled AND clipped (best of both worlds)
    # Clip vol-scaled returns to ±3σ for outlier robuskept for diagnostics)
    # Clip vol-scaled returns to ±3σ for outlier robustness
    y_1d_vol_clip = y_1d_vol.clip(-3.0, 3.0)
    y_5d_vol_clip = y_5d_vol.clip(-3.0, 3.0)
    
    # Primary target alias (for default modeling)
    primary_target = y_1d_vol_clip
    
    # BINARY CLASSIFICATION TARGET (v3.0 - UP/DOWN ONLY)
    # Simple binary classification: did price go up or down?
    # Two classes: 1 (UP), -1 (DOWN)
    y_class_1d = pd.Series(-1, index=y_1d_raw.index, dtype=int)  # Default: DOWN
    y_class_1d[y_1d_raw > 0] = 1   # Positive return → UP
    y_class_1d[y_1d_raw <= 0] = -1  # Negative or zero return → DOWN
    # NaN handling
    y_class_1d = y_class_1d.where(y_1d_raw.notna(), None)  # NaN where input is NaN
    
    # 5-DAY BINARY CLASSIFICATION TARGET
    # Same binary method but predicting 5 days ahead
    y_class_5d = pd.Series(-1, index=y_5d_raw.index, dtype=int)  # Default: DOWN
    y_class_5d[y_5d_raw > 0] = 1   # Positive return → UP
    y_class_5d[y_5d_raw <= 0] = -1  # Negative or zero return → DOWN
    y_class_5d = y_class_5d.where(y_5d_raw.notna(), None)  # NaN where input is NaN
    
    # Binary classification targets (legacy, for comparison)
    y_1d_class = (future_1d > close).astype(int)
    y_5d_class = (future_5d > close).astype(int)
    ret_1d = (future_1d / close - 1.0)
    y_thresh_class = (ret_1d > y_thresh).astype(int)
    
    labels = pd.DataFrame({
        # PRIMARY REGRESSION TARGETS (optimized)
        "primary_target": primary_target,
        "y_1d_vol_clip": y_1d_vol_clip,
        "y_5d_vol_clip": y_5d_vol_clip,
        
        # TRIPLE-BARRIER CLASSIFICATION TARGETS
        "y_class_1d": y_class_1d,  # 1-day (next day)
        "y_class_5d": y_class_5d,  # 5-day (weekly)
        
        # Diagnostic targets
        "y_1d_raw": y_1d_raw,
        "y_5d_raw": y_5d_raw,
        "y_1d_vol": y_1d_vol,
        "y_5d_vol": y_5d_vol,
        "y_1d_clipped": y_1d_clipped,
        "y_5d_clipped": y_5d_clipped,
        
        # Binary classification targets (LEGACY)
        "y_1d": y_1d_class,
        "y_5d": y_5d_class,
        "y_thresh": y_thresh_class,
    })
    
    # Drop last rows where future labels not available
    labels = labels.iloc[:-5] if len(labels) >= 5 else labels.iloc[0:0]
    return labels
