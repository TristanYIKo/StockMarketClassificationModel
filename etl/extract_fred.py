"""
FRED data extraction with strict ET timezone alignment.

Critical rules:
- FRED observations are date-based (no intraday timestamps)
- Each observation is available at END of that calendar day in ET
- Convert all dates to ET trading dates using NYSE calendar
- Forward-fill sparse/weekly series ONLY within max gap (7 calendar days)
- Track days_since_update to avoid false precision
"""

from datetime import datetime, timedelta
import os
import pandas as pd
import numpy as np
from typing import Dict, Optional
from zoneinfo import ZoneInfo

try:
    from fredapi import Fred
except ImportError:
    Fred = None

ET_TZ = ZoneInfo("America/New_York")

# FRED series metadata
FRED_SERIES_CONFIG = {
    "DGS2": {"name": "2Y Treasury Yield", "units": "percent", "frequency": "daily"},
    "DGS10": {"name": "10Y Treasury Yield", "units": "percent", "frequency": "daily"},
    "FEDFUNDS": {"name": "Federal Funds Rate", "units": "percent", "frequency": "monthly"},
    "EFFR": {"name": "Effective Federal Funds Rate", "units": "percent", "frequency": "daily"},
    "T10YIE": {"name": "10Y Breakeven Inflation", "units": "percent", "frequency": "daily"},
    "BAMLH0A0HYM2": {"name": "High Yield OAS", "units": "percent", "frequency": "daily"},
    "WALCL": {"name": "Fed Total Assets", "units": "millions_usd", "frequency": "weekly"},
    "RRPONTSYD": {"name": "ON RRP Usage", "units": "billions_usd", "frequency": "daily"},
    "SOFR": {"name": "Secured Overnight Financing Rate", "units": "percent", "frequency": "daily"},
}


def get_fred_client() -> Optional[Fred]:
    """Initialize FRED client with API key from environment."""
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY environment variable not set")
    if Fred is None:
        raise ImportError("fredapi not installed. Run: pip install fredapi")
    return Fred(api_key=api_key)


def align_to_et_trading_date(date_series: pd.Series, nyse_calendar) -> pd.Series:
    """
    Convert calendar dates to ET trading dates.
    
    If date falls on a non-trading day, roll forward to next trading day.
    This ensures all FRED observations are aligned to when they'd be usable in trading.
    """
    dates = pd.to_datetime(date_series).dt.date
    trading_dates = []
    
    schedule = nyse_calendar.schedule(
        start_date=dates.min(),
        end_date=dates.max() + timedelta(days=10)  # buffer for roll-forward
    )
    valid_trading_days = set(schedule.index.date)
    
    for d in dates:
        # If observation date is a trading day, use it
        if d in valid_trading_days:
            trading_dates.append(d)
        else:
            # Roll forward to next trading day
            candidate = d + timedelta(days=1)
            while candidate not in valid_trading_days and (candidate - d).days < 7:
                candidate = candidate + timedelta(days=1)
            if candidate in valid_trading_days:
                trading_dates.append(candidate)
            else:
                trading_dates.append(None)  # Skip if no trading day within 7 days
    
    return pd.Series(trading_dates, index=date_series.index)


def forward_fill_with_tracking(df: pd.DataFrame, max_gap_days: int = 7) -> pd.DataFrame:
    """
    Forward-fill sparse series within max gap and track days_since_update.
    
    Returns DataFrame with columns: date, value, days_since_update
    """
    df = df.copy().sort_values("date")
    df["days_since_update"] = 0
    
    # Create full date range
    all_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    full_df = pd.DataFrame({"date": all_dates})
    full_df["date"] = full_df["date"].dt.date
    
    # Merge with observations
    merged = full_df.merge(df, on="date", how="left")
    
    # Track last observed value and days since
    last_value = None
    days_since = 0
    results = []
    
    for _, row in merged.iterrows():
        if pd.notna(row["value"]):
            # Actual observation
            last_value = row["value"]
            days_since = 0
            results.append({"date": row["date"], "value": last_value, "days_since_update": 0})
        elif last_value is not None and days_since < max_gap_days:
            # Forward-fill within gap
            days_since += 1
            results.append({"date": row["date"], "value": last_value, "days_since_update": days_since})
        else:
            # Gap too large or no prior value
            days_since += 1
    
    return pd.DataFrame(results)


def download_fred_series(
    series_id: str,
    start: str,
    end: str,
    nyse_calendar,
    max_gap_days: int = 7
) -> pd.DataFrame:
    """
    Download FRED series with ET alignment.
    
    Returns DataFrame with columns: date, value, days_since_update
    All dates are ET trading dates.
    """
    fred = get_fred_client()
    
    try:
        series = fred.get_series(series_id, observation_start=start, observation_end=end)
    except Exception as e:
        print(f"Warning: Failed to fetch {series_id}: {e}")
        return pd.DataFrame({"date": [], "value": [], "days_since_update": []})
    
    if series.empty:
        return pd.DataFrame({"date": [], "value": [], "days_since_update": []})
    
    # Convert to DataFrame
    df = series.reset_index()
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    
    # Align to ET trading dates
    df["date"] = align_to_et_trading_date(df["date"], nyse_calendar)
    df = df[df["date"].notna()].drop_duplicates(subset=["date"])
    
    # Forward-fill within gap and track updates
    df = forward_fill_with_tracking(df, max_gap_days=max_gap_days)
    
    # Filter to NYSE trading days only
    schedule = nyse_calendar.schedule(start_date=start, end_date=end)
    valid_trading_days = set(schedule.index.date)
    df = df[df["date"].isin(valid_trading_days)]
    
    return df


def compute_fred_derived_features(macro_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Compute derived macro features from FRED series.
    
    Returns DataFrame with date and derived columns.
    """
    # Merge all series on date
    dfs = []
    for series_id, df in macro_dict.items():
        if not df.empty:
            df_copy = df[["date", "value"]].copy()
            df_copy = df_copy.rename(columns={"value": series_id})
            dfs.append(df_copy)
    
    if not dfs:
        return pd.DataFrame()
    
    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.merge(df, on="date", how="outer")
    
    merged = merged.sort_values("date")
    
    # Rename raw FRED series to lowercase for consistency
    if "DGS10" in merged.columns:
        merged["dgs10"] = merged["DGS10"]
    if "DGS2" in merged.columns:
        merged["dgs2"] = merged["DGS2"]
    
    # Derived features
    if "DGS10" in merged.columns and "DGS2" in merged.columns:
        merged["yield_curve_slope"] = merged["DGS10"] - merged["DGS2"]
    
    if "DGS10" in merged.columns:
        merged["dgs10_change_1d"] = merged["DGS10"].shift(1).diff(1)
        merged["dgs10_change_5d"] = merged["DGS10"].shift(1).diff(5)
    
    if "DGS2" in merged.columns:
        merged["dgs2_change_1d"] = merged["DGS2"].shift(1).diff(1)
        merged["dgs2_change_5d"] = merged["DGS2"].shift(1).diff(5)
    
    if "BAMLH0A0HYM2" in merged.columns:
        merged["hy_oas_level"] = merged["BAMLH0A0HYM2"]
        merged["hy_oas_change_1d"] = merged["BAMLH0A0HYM2"].shift(1).diff(1)
        merged["hy_oas_change_5d"] = merged["BAMLH0A0HYM2"].shift(1).diff(5)
    
    if "WALCL" in merged.columns:
        merged["fed_balance_sheet_change_pct"] = merged["WALCL"].shift(1).pct_change(periods=5)
        # Liquidity regime: expanding if 20d change > 0
        merged["liquidity_expanding"] = (merged["WALCL"].shift(1).diff(20) > 0).astype(int)
    
    if "RRPONTSYD" in merged.columns:
        merged["rrp_level"] = merged["RRPONTSYD"]
        merged["rrp_change_pct_5d"] = merged["RRPONTSYD"].shift(1).pct_change(periods=5)
    
    return merged
