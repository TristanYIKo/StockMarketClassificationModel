import argparse
from datetime import date
import os
import pandas as pd
import pandas_market_calendars as mcal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .config import ETLConfig
from .supabase_client import SupabaseDB
from .extract_yf import download_ohlcv, download_actions
from .extract_fred import download_fred_series, compute_fred_derived_features, FRED_SERIES_CONFIG
from .extract_proxies import download_proxy_ohlcv, compute_proxy_features, compute_relative_strength_features, PROXY_TICKERS
from .build_events import build_events_calendar
from .transform_features import compute_features
from .transform_features_context import merge_context_features, create_modeling_features_json, forward_fill_macro_conservative
from .transform_lags import apply_lags
from .transform_regimes import compute_all_regimes
from .transform_labels import compute_labels
from .load_db import (
    upsert_asset_metadata,
    upsert_daily,
    upsert_actions,
    upsert_features_json,
    upsert_labels,
    upsert_macro_catalog,
    upsert_macro_daily,
)


def upsert_events(db: SupabaseDB, events_df: pd.DataFrame):
    """Upsert events calendar."""
    data = [
        {
            "date": str(r.date),
            "event_type": r.event_type,
            "event_name": r.event_name,
            "source": r.source
        }
        for r in events_df.itertuples(index=False)
    ]
    if data:
        for item in data:
            db.client.table("events_calendar").upsert(item, on_conflict="date,event_type").execute()


def run_etl(start: str, end: str, mode: str):
    cfg = ETLConfig(start=date.fromisoformat(start), end=date.fromisoformat(end), mode=mode)
    db = SupabaseDB()
    
    # Initialize NYSE calendar for ET alignment
    nyse = mcal.get_calendar("NYSE")

    # 1. Assets: ETFs + proxies
    all_symbols = list(cfg.symbols) + list(PROXY_TICKERS.keys())
    asset_rows = []
    for sym in cfg.symbols:
        asset_rows.append((sym, sym, "ETF", "NYSE/NASDAQ", "USD"))
    for sym, meta in PROXY_TICKERS.items():
        asset_rows.append((sym, meta["name"], meta["asset_type"], "NYSE/NASDAQ", "USD"))
    
    upsert_asset_metadata(db, asset_rows)
    asset_id_map = db.get_asset_id_map()

    # 2. Extract ETF bars and actions
    etf_bars_dict = {}
    for sym in cfg.symbols:
        print(f"Processing ETF {sym} ...")
        bars = download_ohlcv(sym, start, end)
        actions = download_actions(sym, start, end)
        if bars.empty:
            print(f"No bars for {sym}")
            continue
        etf_bars_dict[sym] = bars
        upsert_daily(db, asset_id_map[sym], bars)
        if not actions.empty:
            upsert_actions(db, asset_id_map[sym], actions)
        print(f"Done {sym}: bars={len(bars)}")

    # 3. Extract proxy OHLCV
    proxy_bars_dict = {}
    for sym in PROXY_TICKERS.keys():
        print(f"Processing proxy {sym} ...")
        bars = download_proxy_ohlcv(sym, start, end)
        if bars.empty:
            print(f"No bars for proxy {sym}")
            continue
        proxy_bars_dict[sym] = bars
        upsert_daily(db, asset_id_map[sym], bars)
        print(f"Done proxy {sym}: bars={len(bars)}")

    # 4. Extract FRED macro series with ET alignment
    print("Processing FRED macro series ...")
    macro_dict = {}
    for series_id in cfg.fred_series:
        print(f"  Fetching {series_id} ...")
        df = download_fred_series(series_id, start, end, nyse, max_gap_days=7)
        if df.empty:
            print(f"  No data for {series_id}")
            continue
        macro_dict[series_id] = df
        print(f"  Done {series_id}: rows={len(df)}")
    
    # Upsert macro catalog
    macro_catalog_rows = [
        (series_id, FRED_SERIES_CONFIG.get(series_id, {}).get("name", series_id), 
         FRED_SERIES_CONFIG.get(series_id, {}).get("frequency", "daily"), "FRED")
        for series_id in cfg.fred_series
    ]
    db.upsert_macro_series(macro_catalog_rows)
    macro_id_map = db.get_macro_series_id_map()
    
    for series_id, df in macro_dict.items():
        if series_id in macro_id_map:
            upsert_macro_daily(db, macro_id_map[series_id], df)

    # 5. Build events calendar
    print("Building events calendar ...")
    events_df = build_events_calendar(nyse, start, end)
    if not events_df.empty:
        upsert_events(db, events_df)
        print(f"Done events: rows={len(events_df)}")

    # 6. Compute derived features from FRED and proxies
    print("Computing context features ...")
    macro_features_df = compute_fred_derived_features(macro_dict)
    
    # Add SPY to proxy dict for relative strength calculations
    proxy_with_spy = {**proxy_bars_dict, "SPY": etf_bars_dict.get("SPY", pd.DataFrame())}
    proxy_features_df = compute_proxy_features(proxy_with_spy)
    relative_strength_df = compute_relative_strength_features(etf_bars_dict)

    # 7. For each ETF: REGRESSION FEATURE PIPELINE
    # Execution order (CRITICAL for no leakage):
    #   1) Load raw data
    #   2) Compute base technical features
    #   3) Merge context features (macro, proxies, events)
    #   4) Compute rolling stats (overnight/intraday, ADX, etc)
    #   5) Compute regime flags
    #   6) Apply lags (LAST, provides memory)
    #   7) Compute labels (forward-shifted)
    
    for sym in cfg.symbols:
        if sym not in etf_bars_dict:
            continue
        
        print(f"Building regression features for {sym} ...")
        bars = etf_bars_dict[sym]
        
        # STEP 1: Base technical features from OHLCV
        # Includes: returns, RSI, MACD, SMA/EMA, ATR, volume, drawdown, calendar
        # NEW: overnight/intraday returns, ADX, autocorr, R²
        tech_features = compute_features(bars)
        
        # STEP 2: Merge context features (macro, proxies, breadth, events)
        # Adds: FRED macro, VIX, cross-asset, relative strength, event flags
        full_features = merge_context_features(
            tech_features,
            macro_features_df,
            proxy_features_df,
            relative_strength_df,
            events_df
        )
        
        # STEP 3: Conservative forward-fill for macro (max 5-day gaps)
        full_features = forward_fill_macro_conservative(full_features, max_gap_days=5)
        
        # STEP 4: Compute regime flags
        # Adds: high_vol_regime, curve_inverted, credit_stress, liquidity_expanding_regime
        full_features = compute_all_regimes(full_features)
        
        # STEP 5: Apply temporal lags (memory for regression)
        # Adds: log_ret_1d_lag1/2/3/5, vix_change_lag1/3, hy_oas_change_lag1, yield_curve_slope_lag1
        full_features = apply_lags(full_features)
        
        # STEP 6: Convert to feature_json format for storage
        features_json_df = create_modeling_features_json(full_features)
        upsert_features_json(db, asset_id_map[sym], features_json_df)
        
        # STEP 7: Compute regression labels (volatility-scaled, forward-shifted)
        # Needs vol_20 from features for scaling
        vol_20 = full_features["vol_20"]
        labels = compute_labels(bars["close"], vol_20, y_thresh=cfg.y_thresh)
        labels.index = pd.to_datetime(bars["date"])[: len(labels)].dt.date
        labels.index.name = "date"
        upsert_labels(db, asset_id_map[sym], labels)
        
        print(f"Done {sym}: features={len(features_json_df)}, labels={len(labels)}")

    db.close()
    print("ETL complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, required=True)
    parser.add_argument("--end", type=str, required=True)
    parser.add_argument("--mode", type=str, choices=["backfill", "incremental"], default="backfill")
    args = parser.parse_args()

    run_etl(args.start, args.end, args.mode)
