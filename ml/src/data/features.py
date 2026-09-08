"""
Turn absolute price levels into scale-free features.

Why this exists
---------------
The ETL stores raw levels: close, sma_20/50/200, ema_20/50, rolling_max_60,
atr_14, tr, and the proxy closes (SPY_close, GLD_close, TLT_close, ...).

Splits here are chronological: train is 2001-2023, test is 2025-2026. SPY closed
at ~130 in 2001 and ~770 in 2026, so *every* test value of `sma_200` lies outside
the range the trees ever saw. A threshold like `sma_200 < 450` sends the entire
test set down one branch, and the model degenerates to a near-constant predictor
regardless of how well it fit in-sample. This is the standard reason a
chronologically-split price model scores below its own base rate out of sample.

The fix is to express each level relative to a contemporaneous denominator, so
the feature means the same thing in 2001 and 2026. Ratios, returns, z-scores and
bounded levels (VIX, yields, credit spreads) are already scale-free and pass
through untouched.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Levels replaced by `close`-relative distance.
_PRICE_LEVELS = ["sma_20", "sma_50", "sma_200", "ema_20", "ema_50", "rolling_max_60"]

# Levels rescaled by `close` into a percentage-of-price.
_PRICE_SCALED = ["atr_14", "tr"]

# Proxy closes: dropped outright. Their information is already carried by the
# *_ret_1d/5d/20d columns the ETL computes, and by vix_level / vix_term_structure.
_PROXY_CLOSES = [
    "SPY_close", "GLD_close", "USO_close", "TLT_close", "HYG_close",
    "LQD_close", "UUP_close", "RSP_close",
    "^VIX_close", "^VIX9D_close", "^VVIX_close",
]


def to_stationary_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Replace non-stationary level columns with scale-free equivalents.

    Returns the transformed frame and the list of engineered column names.
    `close` itself is consumed as a denominator and then dropped from features
    (it stays available to the caller under `close` for reporting).
    """
    out = df.copy()
    created: List[str] = []

    if "close" not in out.columns:
        raise ValueError("to_stationary_features needs a `close` column as denominator")

    close = pd.to_numeric(out["close"], errors="coerce")

    # 1. Distance from moving averages, as a fraction of price.
    for col in _PRICE_LEVELS:
        if col not in out.columns:
            continue
        name = f"px_vs_{col}"
        out[name] = pd.to_numeric(out[col], errors="coerce") / close - 1.0
        created.append(name)
        out = out.drop(columns=[col])

    # 2. Moving-average spreads (trend structure without the level).
    if {"px_vs_sma_20", "px_vs_sma_50"} <= set(out.columns):
        out["sma20_vs_sma50"] = out["px_vs_sma_20"] - out["px_vs_sma_50"]
        created.append("sma20_vs_sma50")
    if {"px_vs_sma_50", "px_vs_sma_200"} <= set(out.columns):
        out["sma50_vs_sma200"] = out["px_vs_sma_50"] - out["px_vs_sma_200"]
        created.append("sma50_vs_sma200")

    # 3. Range measures as a percentage of price.
    for col in _PRICE_SCALED:
        if col not in out.columns:
            continue
        name = f"{col}_pct"
        out[name] = pd.to_numeric(out[col], errors="coerce") / close
        created.append(name)
        out = out.drop(columns=[col])

    # 4. Drop proxy price levels outright.
    drop_proxies = [c for c in _PROXY_CLOSES if c in out.columns]
    out = out.drop(columns=drop_proxies)

    out = out.replace([np.inf, -np.inf], np.nan)

    logger.info("Stationarity pass: engineered %d relative features, dropped %d price levels",
                len(created), len(drop_proxies) + len(_PRICE_LEVELS) + len(_PRICE_SCALED))
    logger.info("  created: %s", ", ".join(created))
    logger.info("  dropped proxy levels: %s", ", ".join(drop_proxies) or "none")

    return out, created
