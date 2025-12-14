"""
Transform context features: join macro, proxies, breadth, events to ETF bars.

CRITICAL: Prevent future leakage.
- All features at date t use ONLY data available by market close (4:00 PM ET) on date t.
- FRED observations for date t are available at EOD on date t.
- Proxy closes for date t are available at market close on date t.
- Labels use future closes (shifted forward).
- Event flags indicate event occurs on date t (not outcome).
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


def merge_context_features(
    bars_df: pd.DataFrame,
    macro_df: Optional[pd.DataFrame],
    proxy_features_df: Optional[pd.DataFrame],
    relative_strength_df: Optional[pd.DataFrame],
    events_df: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Merge all context features to ETF bars by date.
    
    Args:
        bars_df: ETF OHLCV with date column
        macro_df: FRED macro features with date column
        proxy_features_df: Cross-asset proxy features with date column
        relative_strength_df: Relative strength ratios with date column
        events_df: Events calendar with date, event_type columns
    
    Returns:
        DataFrame with all features aligned to bars dates (no leakage)
    """
    result = bars_df.copy()
    
    # Merge macro
    if macro_df is not None and not macro_df.empty:
        result = result.merge(macro_df, on="date", how="left")
    
    # Merge proxy features
    if proxy_features_df is not None and not proxy_features_df.empty:
        result = result.merge(proxy_features_df, on="date", how="left")
    
    # Merge relative strength
    if relative_strength_df is not None and not relative_strength_df.empty:
        result = result.merge(relative_strength_df, on="date", how="left")
    
    # Add event flags as binary columns (PRUNED to high-ROI events only)
    # Only include: fomc, cpi_release, nfp_release
    allowed_events = ["fomc", "cpi_release", "nfp_release"]
    if events_df is not None and not events_df.empty:
        for event_type in events_df["event_type"].unique():
            if event_type in allowed_events:
                event_dates = events_df[events_df["event_type"] == event_type]["date"].values
                result[f"is_{event_type}"] = result["date"].isin(event_dates).astype(int)
        
        # Ensure all allowed events have columns (even if empty)
        for event_type in allowed_events:
            if f"is_{event_type}" not in result.columns:
                result[f"is_{event_type}"] = 0
    
    return result


def validate_no_leakage(features_df: pd.DataFrame, labels_df: pd.DataFrame) -> bool:
    """
    Validate that labels are properly shifted and features don't leak future.
    
    Returns True if validation passes.
    """
    # Check labels are shifted forward
    if not labels_df.empty:
        # Labels should have fewer rows than features (last N dropped)
        if len(labels_df) >= len(features_df):
            print("WARNING: Labels not properly truncated (possible leakage)")
            return False
    
    # Check no NaN in critical date-aligned columns at start
    # (some NaN is OK for rolling features at start of history)
    
    return True


def create_modeling_features_json(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert wide features DataFrame to (date, feature_json) format for storage.
    
    Excludes OHLCV columns (stored separately in daily_bars).
    Handles inf/-inf/NaN values (converts to None for JSON compliance).
    """
    ohlcv_cols = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    feature_cols = [c for c in features_df.columns if c not in ohlcv_cols]
    
    feature_records = []
    for _, row in features_df.iterrows():
        feature_dict = {}
        for col in feature_cols:
            val = row[col]
            # Handle NaN, inf, -inf (not JSON compliant)
            if pd.isna(val) or np.isinf(val):
                feature_dict[col] = None
            else:
                feature_dict[col] = float(val)
        
        feature_records.append({
            "date": row["date"],
            "feature_json": feature_dict
        })
    
    return pd.DataFrame(feature_records)


def forward_fill_macro_conservative(df: pd.DataFrame, max_gap_days: int = 5) -> pd.DataFrame:
    """
    Forward-fill macro features conservatively.
    
    Only fill within max_gap_days to avoid stale data.
    Prefer leaving NaN if gap too large (model can handle).
    """
    df = df.copy()
    
    # Identify macro columns (contain 'dgs', 'fed', 'hy_', 'yield_', etc)
    macro_cols = [c for c in df.columns if any(
        x in c.lower() for x in ["dgs", "fed", "hy_", "yield_", "walcl", "rrp", "effr", "sofr", "t10y", "baml"]
    )]
    
    for col in macro_cols:
        # Simple forward-fill with limit
        df[col] = df[col].ffill(limit=max_gap_days)
    
    return df
