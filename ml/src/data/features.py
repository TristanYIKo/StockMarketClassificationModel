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


# FRED values that the ETL stamps with their OBSERVATION date and uses unlagged.
# None of them is published by the time a day's call is made:
#   DGS2 / DGS10 / T10YIE  -- H.15, posted on FRED the next business day
#   EFFR / SOFR            -- next business morning
#   BAMLH0A0HYM2 (HY OAS)  -- next business day
#   WALCL                  -- Wednesday's level, released Thursday 4:30pm ET
# plus every column derived from them at the same date. In the historical
# backfill each row holds the same-day value, which the live job cannot have
# had; rows the incremental ETL wrote hold the previous day's value instead,
# because the new observation was not out yet. Lagging one session makes every
# row use only what was published by that day's close. (Columns the ETL already
# builds from `.shift(1)` -- the *_change_* and *_lag1 columns, liquidity_* and
# fed_balance_sheet_change_pct -- are already safe and are not shifted again.)
_FRED_SAME_DAY = [
    "DGS2", "DGS10", "EFFR", "T10YIE", "BAMLH0A0HYM2", "WALCL", "SOFR",
    "RRPONTSYD", "FEDFUNDS",
    "dgs2", "dgs10", "hy_oas_level", "rrp_level", "yield_curve_slope",
    "curve_inverted", "credit_stress",
]


def apply_publication_lag(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Shift same-day FRED columns back one session per symbol. See _FRED_SAME_DAY."""
    out = df.copy()
    cols = [c for c in _FRED_SAME_DAY if c in out.columns]
    if not cols:
        return out, []
    ordered = out.sort_values(["symbol", "date"])
    out[cols] = ordered.groupby("symbol", sort=False)[cols].shift(1)
    return out, cols


def to_stationary_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Replace non-stationary level columns with scale-free equivalents.

    Also applies the FRED publication lag first, since this is the one
    transform both training and inference run on the dataset.

    Returns the transformed frame and the list of engineered column names.
    `close` itself is consumed as a denominator and then dropped from features
    (it stays available to the caller under `close` for reporting).
    """
    out, lagged = apply_publication_lag(df)
    if lagged:
        logger.info("Publication lag: shifted %d same-day FRED columns back one session",
                    len(lagged))
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
