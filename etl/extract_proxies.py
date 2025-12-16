"""
Extract cross-asset and risk proxy data with ET alignment.

Proxies:
- VIX complex: ^VIX, ^VIX9D, ^VVIX
- DXY: UUP ETF (more liquid than DXY futures)
- Gold: GLD
- Oil: USO (ETF, more consistent than CL=F futures)
- Credit: HYG, LQD
- Bonds: TLT
- Breadth: RSP (equal-weight S&P)

All bars represent NYSE close (4:00 PM ET).
"""

from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf
from zoneinfo import ZoneInfo

ET_TZ = ZoneInfo("America/New_York")

# Proxy ticker definitions
PROXY_TICKERS = {
    # Volatility
    "^VIX": {"name": "CBOE Volatility Index", "asset_type": "index"},
    "^VIX9D": {"name": "CBOE 9-Day Volatility", "asset_type": "index"},
    "^VVIX": {"name": "CBOE VIX of VIX", "asset_type": "index"},
    
    # Currency
    "UUP": {"name": "Dollar Index ETF", "asset_type": "etf"},
    
    # Commodities
    "GLD": {"name": "Gold ETF", "asset_type": "etf"},
    "USO": {"name": "Oil ETF", "asset_type": "etf"},
    
    # Credit
    "HYG": {"name": "High Yield Corporate Bonds ETF", "asset_type": "etf"},
    "LQD": {"name": "Investment Grade Corporate Bonds ETF", "asset_type": "etf"},
    
    # Bonds
    "TLT": {"name": "20+ Year Treasury ETF", "asset_type": "etf"},
    
    # Breadth
    "RSP": {"name": "Equal Weight S&P 500 ETF", "asset_type": "etf"},
}


def download_proxy_ohlcv(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    Download OHLCV for proxy ticker with ET alignment.
    
    Returns DataFrame with columns: date, open, high, low, close, adj_close, volume
    All dates are NYSE trading days.
    """
    # yfinance end date is exclusive, so add 1 day to include the end date
    from datetime import datetime, timedelta
    end_date = datetime.fromisoformat(end) + timedelta(days=1)
    end_inclusive = end_date.strftime("%Y-%m-%d")
    df = yf.download(symbol, start=start, end=end_inclusive, interval="1d", auto_adjust=False, progress=False)
    
    if df.empty:
        return pd.DataFrame({"date": [], "open": [], "high": [], "low": [], "close": [], "adj_close": [], "volume": []})
    
    # Handle MultiIndex columns (yfinance returns this for single symbols)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    
    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    })
    
    # Ensure dates are ET trading days
    df.index = pd.to_datetime(df.index).tz_localize(ET_TZ).date
    df = df.reset_index().rename(columns={"index": "date"})
    
    return df[["date", "open", "high", "low", "close", "adj_close", "volume"]]


def compute_proxy_features(proxy_dict: dict, base_symbols: list = ["SPY"]) -> pd.DataFrame:
    """
    Compute features from proxy data:
    - VIX level, change, term structure
    - Cross-asset returns and momentum
    - Relative strength vs SPY
    - Rolling correlations
    
    Returns DataFrame with date and feature columns.
    """
    # Merge all proxies on date
    dfs = []
    for symbol, df in proxy_dict.items():
        if not df.empty and "close" in df.columns:
            df_copy = df[["date", "close"]].copy()
            df_copy = df_copy.rename(columns={"close": f"{symbol}_close"})
            dfs.append(df_copy)
    
    if not dfs:
        return pd.DataFrame()
    
    merged = dfs[0]
    for df in dfs[1:]:
        merged = merged.merge(df, on="date", how="outer")
    
    merged = merged.sort_values("date")
    
    # VIX features
    if "^VIX_close" in merged.columns:
        merged["vix_level"] = merged["^VIX_close"]
        merged["vix_change_1d"] = merged["^VIX_close"].shift(1).diff(1)
        merged["vix_change_5d"] = merged["^VIX_close"].shift(1).diff(5)
        merged["vix_pct_change_1d"] = merged["^VIX_close"].shift(1).pct_change(1)
        
        # VIX term structure proxy
        if "^VIX9D_close" in merged.columns:
            merged["vix_term_structure"] = merged["^VIX_close"] - merged["^VIX9D_close"]
    
    # DXY (UUP) features
    if "UUP_close" in merged.columns:
        merged["dxy_ret_1d"] = merged["UUP_close"].shift(1).pct_change(1)
        merged["dxy_ret_5d"] = merged["UUP_close"].shift(1).pct_change(5)
        merged["dxy_ret_20d"] = merged["UUP_close"].shift(1).pct_change(20)
    
    # Gold features
    if "GLD_close" in merged.columns:
        merged["gold_ret_1d"] = merged["GLD_close"].shift(1).pct_change(1)
        merged["gold_ret_5d"] = merged["GLD_close"].shift(1).pct_change(5)
        merged["gold_ret_20d"] = merged["GLD_close"].shift(1).pct_change(20)
    
    # Oil features
    if "USO_close" in merged.columns:
        merged["oil_ret_1d"] = merged["USO_close"].shift(1).pct_change(1)
        merged["oil_ret_5d"] = merged["USO_close"].shift(1).pct_change(5)
        merged["oil_ret_20d"] = merged["USO_close"].shift(1).pct_change(20)
    
    # Credit features
    if "HYG_close" in merged.columns:
        merged["hyg_ret_1d"] = merged["HYG_close"].shift(1).pct_change(1)
        merged["hyg_ret_5d"] = merged["HYG_close"].shift(1).pct_change(5)
        merged["hyg_ret_20d"] = merged["HYG_close"].shift(1).pct_change(20)
        
        # Relative to SPY (if available)
        if "SPY_close" in merged.columns:
            merged["hyg_vs_spy_5d"] = merged["hyg_ret_5d"] - merged["SPY_close"].pct_change(5)
            # Rolling correlation
            merged["hyg_spy_corr_20d"] = merged["HYG_close"].pct_change(1).rolling(20).corr(
                merged["SPY_close"].pct_change(1)
            )
    
    if "LQD_close" in merged.columns:
        merged["lqd_ret_1d"] = merged["LQD_close"].pct_change(1)
        merged["lqd_ret_5d"] = merged["LQD_close"].pct_change(5)
        merged["lqd_ret_20d"] = merged["LQD_close"].pct_change(20)
    
    # TLT features
    if "TLT_close" in merged.columns:
        merged["tlt_ret_1d"] = merged["TLT_close"].pct_change(1)
        merged["tlt_ret_5d"] = merged["TLT_close"].pct_change(5)
        merged["tlt_ret_20d"] = merged["TLT_close"].pct_change(20)
    
    # Breadth: RSP vs SPY
    if "RSP_close" in merged.columns and "SPY_close" in merged.columns:
        merged["rsp_spy_ratio"] = merged["RSP_close"] / merged["SPY_close"]
        merged["rsp_spy_ratio_ma20"] = merged["rsp_spy_ratio"].rolling(20).mean()
        merged["rsp_spy_ratio_z"] = (
            (merged["rsp_spy_ratio"] - merged["rsp_spy_ratio_ma20"]) /
            merged["rsp_spy_ratio"].rolling(20).std()
        )
    
    return merged


def compute_relative_strength_features(etf_dict: dict) -> pd.DataFrame:
    """
    Compute relative strength between ETFs (QQQ/SPY, IWM/SPY).
    
    etf_dict: {symbol: DataFrame with date, close}
    """
    if "SPY" not in etf_dict or "QQQ" not in etf_dict:
        return pd.DataFrame()
    
    spy = etf_dict["SPY"][["date", "close"]].rename(columns={"close": "SPY_close"})
    qqq = etf_dict.get("QQQ", pd.DataFrame())
    iwm = etf_dict.get("IWM", pd.DataFrame())
    
    merged = spy.copy()
    
    if not qqq.empty:
        qqq_df = qqq[["date", "close"]].rename(columns={"close": "QQQ_close"})
        merged = merged.merge(qqq_df, on="date", how="outer")
        merged["qqq_spy_ratio"] = merged["QQQ_close"] / merged["SPY_close"]
        merged["qqq_spy_ratio_ma20"] = merged["qqq_spy_ratio"].rolling(20).mean()
        merged["qqq_spy_ratio_z"] = (
            (merged["qqq_spy_ratio"] - merged["qqq_spy_ratio_ma20"]) /
            merged["qqq_spy_ratio"].rolling(20).std()
        )
    
    if not iwm.empty:
        iwm_df = iwm[["date", "close"]].rename(columns={"close": "IWM_close"})
        merged = merged.merge(iwm_df, on="date", how="outer")
        merged["iwm_spy_ratio"] = merged["IWM_close"] / merged["SPY_close"]
        merged["iwm_spy_ratio_ma20"] = merged["iwm_spy_ratio"].rolling(20).mean()
        merged["iwm_spy_ratio_z"] = (
            (merged["iwm_spy_ratio"] - merged["iwm_spy_ratio_ma20"]) /
            merged["iwm_spy_ratio"].rolling(20).std()
        )
    
    # Drop the raw close columns, keep only ratios
    cols_to_drop = [c for c in merged.columns if c.endswith("_close")]
    merged = merged.drop(columns=cols_to_drop)
    
    return merged
