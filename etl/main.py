import argparse
from datetime import date, timedelta
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
    db = SupabaseDB()
    nyse = mcal.get_calendar("NYSE")
    
    # 0. Auto-detect start date if not provided
    if start is None:
        # Check all critical tables for last date
        tables = ['daily_bars', 'features_daily', 'labels_daily']
        last_dates = []
        
        for table in tables:
            try:
                response = db.client.table(table)\
                    .select('date')\
                    .order('date', desc=True)\
                    .limit(1)\
                    .execute()
                
                if response.data and len(response.data) > 0:
                    date_str = response.data[0]['date']
                    if 'T' in date_str:
                        date_str = date_str.split('T')[0]
                    last_dates.append(date.fromisoformat(date_str))
                    print(f"  {table}: last date = {date_str}")
            except Exception as e:
                print(f"  Warning: Could not check {table}: {e}")
        
        if last_dates:
            # Use the minimum date across tables to ensure consistency
            latest = min(last_dates)
            print(f"✅ Last complete date in DB: {latest}")
            
            # Find the next trading day after latest
            end_date_temp = date.fromisoformat(end)
            schedule = nyse.schedule(start_date=latest, end_date=end_date_temp)
            
            if len(schedule) <= 1:
                # No new trading days
                print(f"✅ Database is up to date. Last date: {latest}, End date: {end_date_temp}")
                print("No new trading days to process.")
                return
            
            # Get next trading day after latest
            next_trading_day = schedule.index[1].date()
            start = next_trading_day.isoformat()
            print(f"✅ Auto-detected update start date: {start} (next trading day after {latest})")
            mode = "incremental"
        else:
            start = "2015-01-01"
            print(f"⚠️ No data in DB. Defaulting to backfill from {start}")
            mode = "backfill"

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    
    # Verify we have trading days in the range
    schedule = nyse.schedule(start_date=start_date, end_date=end_date)
    if len(schedule) == 0:
        print(f"⚠️ No trading days between {start_date} and {end_date}. Nothing to update.")
        return
    
    print(f"📊 Processing {len(schedule)} trading days from {start_date} to {end_date}")
    
    # Lookback window for rolling features (ensures 200-day MA is correct)
    LOOKBACK_DAYS = 365
    context_start_date = start_date - timedelta(days=LOOKBACK_DAYS)
    context_start_str = context_start_date.isoformat()
    
    print(f"Configuration: Range {start} to {end} | Mode: {mode}")
    print(f"Context Lookback: {context_start_str} (to ensure feature correctness)")

    cfg = ETLConfig(start=start_date, end=end_date, mode=mode)
    
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

    # 2. Extract ETF bars and actions (WITH LOOKBACK)
    etf_bars_dict = {}
    for sym in cfg.symbols:
        print(f"Processing ETF {sym} ...")
        
        # A. Fetch History (Context)
        hist_data = []
        if mode == "incremental":
            hist_data = db.fetch_daily_bars(asset_id_map[sym], context_start_str)
            # Filter strictly before start_date to avoid dups
            hist_data = [d for d in hist_data if d['date'] < start]
        
        hist_df = pd.DataFrame(hist_data)
        if not hist_df.empty:
            # Convert date to datetime for consistency with downloaded data
            hist_df['date'] = pd.to_datetime(hist_df['date'])
            # Ensure numeric columns
            for col in ['open', 'high', 'low', 'close', 'adj_close', 'volume']:
                 hist_df[col] = pd.to_numeric(hist_df[col])
        
        # B. Download New Data
        new_bars = download_ohlcv(sym, start, end)
        actions = download_actions(sym, start, end)
        
        # Upsert NEW data immediately (raw data is safe to upsert)
        if not new_bars.empty:
            upsert_daily(db, asset_id_map[sym], new_bars)
        if not actions.empty:
            upsert_actions(db, asset_id_map[sym], actions)
            
        # C. Merge for Feature Computation
        if not new_bars.empty:
            # Normalize dates
            new_bars['date'] = pd.to_datetime(new_bars['date'])
            if not hist_df.empty:
                full_bars = pd.concat([hist_df, new_bars]).drop_duplicates(subset='date').sort_values('date').reset_index(drop=True)
            else:
                full_bars = new_bars
        else:
            full_bars = hist_df
            
        if full_bars.empty:
            print(f"  No data for {sym} (History: {len(hist_df)}, New: {len(new_bars)})")
            continue
            
        etf_bars_dict[sym] = full_bars
        print(f"  Merged {sym}: {len(full_bars)} rows (History: {len(hist_df)}, New: {len(new_bars)})")

    # 3. Extract proxy OHLCV (WITH LOOKBACK)
    proxy_bars_dict = {}
    for sym in PROXY_TICKERS.keys():
        print(f"Processing proxy {sym} ...")
        
        # A. Fetch History
        hist_data = []
        if mode == "incremental":
            # Proxies are stored in daily_bars too? Yes, asset_id_map includes them.
            hist_data = db.fetch_daily_bars(asset_id_map[sym], context_start_str)
            hist_data = [d for d in hist_data if d['date'] < start]
            
        hist_df = pd.DataFrame(hist_data)
        if not hist_df.empty:
            hist_df['date'] = pd.to_datetime(hist_df['date'])
            for col in ['open', 'high', 'low', 'close', 'adj_close', 'volume']:
                 hist_df[col] = pd.to_numeric(hist_df[col])

        # B. Download New
        new_bars = download_proxy_ohlcv(sym, start, end)
        
        if not new_bars.empty:
            upsert_daily(db, asset_id_map[sym], new_bars)
            new_bars['date'] = pd.to_datetime(new_bars['date'])
        
        # C. Merge
        if not new_bars.empty:
             if not hist_df.empty:
                full_bars = pd.concat([hist_df, new_bars]).drop_duplicates(subset='date').sort_values('date').reset_index(drop=True)
             else:
                full_bars = new_bars
        else:
            full_bars = hist_df
        
        if full_bars.empty:
            continue
            
        proxy_bars_dict[sym] = full_bars

    # 4. Extract FRED macro series (WITH LOOKBACK)
    print("Processing FRED macro series ...")
    
    # Upsert macro catalog first
    macro_catalog_rows = [
        (series_id, FRED_SERIES_CONFIG.get(series_id, {}).get("name", series_id), 
         FRED_SERIES_CONFIG.get(series_id, {}).get("frequency", "daily"), "FRED")
        for series_id in cfg.fred_series
    ]
    db.upsert_macro_series(macro_catalog_rows)
    macro_id_map = db.get_macro_series_id_map()
    
    macro_dict = {}
    for series_id in cfg.fred_series:
        print(f"  Fetching {series_id} ...")
        
        # A. Fetch History
        hist_data = []
        if mode == "incremental" and series_id in macro_id_map:
            hist_data = db.fetch_macro_daily(macro_id_map[series_id], context_start_str)
            hist_data = [d for d in hist_data if d['date'] < start]
            
        hist_df = pd.DataFrame(hist_data)
        if not hist_df.empty:
            hist_df['date'] = pd.to_datetime(hist_df['date'])
            hist_df['value'] = pd.to_numeric(hist_df['value'])
        
        # B. Download New
        # Note: download_fred_series handles caching/rate limits? 
        # We pass full range because FRED often updates history. 
        # But for strictly incremental, maybe start is enough. 
        # Use context_start for safety with FRED lags? No, download new only.
        new_df = download_fred_series(series_id, start, end, nyse, max_gap_days=7)
        
        if not new_df.empty:
            if series_id in macro_id_map:
                upsert_macro_daily(db, macro_id_map[series_id], new_df)
            new_df['date'] = pd.to_datetime(new_df['date'])
            
        # C. Merge
        if not new_df.empty:
            if not hist_df.empty:
                # FRED might overlap, prioritise new
                full_df = pd.concat([hist_df, new_df]).drop_duplicates(subset='date', keep='last').sort_values('date').reset_index(drop=True)
            else:
                full_df = new_df
        else:
            full_df = hist_df
            
        if not full_df.empty:
            macro_dict[series_id] = full_df

    # 5. Build events calendar (Full Range for context? Events usually future/past known)
    # Just build for new range is fine, or context. Let's do context for safety.
    print("Building events calendar ...")
    events_df = build_events_calendar(nyse, context_start_str, end)
    if not events_df.empty:
        # Upsert only new ones? The upsert logic handles conflicts.
        upsert_events(db, events_df)

    # 6. Compute derived features (On Full Concatenated Data)
    print("Computing context features ...")
    macro_features_df = compute_fred_derived_features(macro_dict)
    
    proxy_with_spy = {**proxy_bars_dict, "SPY": etf_bars_dict.get("SPY", pd.DataFrame())}
    proxy_features_df = compute_proxy_features(proxy_with_spy)
    relative_strength_df = compute_relative_strength_features(etf_bars_dict)

    # 7. For each ETF: FEATURE PIPELINE
    for sym in cfg.symbols:
        if sym not in etf_bars_dict:
            continue
        
        bars = etf_bars_dict[sym]
        if bars.empty:
            continue
            
        print(f"Building regression features for {sym} (Total rows: {len(bars)})...")
        
        # Computation runs on FULL history + new data
        tech_features = compute_features(bars)
        
        full_features = merge_context_features(
            tech_features,
            macro_features_df,
            proxy_features_df,
            relative_strength_df,
            events_df
        )
        
        full_features = forward_fill_macro_conservative(full_features, max_gap_days=5)
        full_features = compute_all_regimes(full_features)
        full_features = apply_lags(full_features)
        
        # --- SLICE NEW DATA FOR UPSERT ---
        # Only upsert rows >= start_date
        # Convert index/date to compare
        full_features['date_temp'] = pd.to_datetime(full_features['date'])
        new_features = full_features[full_features['date_temp'] >= pd.to_datetime(start_date)].copy()
        
        if new_features.empty:
            print(f"  No new features to upsert for {sym}")
            continue
            
        features_json_df = create_modeling_features_json(new_features)
        upsert_features_json(db, asset_id_map[sym], features_json_df)
        
        # Compute Labels
        # Labels need FUTURE data. 
        # If we are at 'today', future labels will be NaN/Wait.
        # But compute_labels handles this.
        vol_20 = full_features["vol_20"]
        
        # Pass FULL bars to compute labels (needs shift)
        labels = compute_labels(bars["close"], vol_20, y_thresh=cfg.y_thresh)
        labels.index = pd.to_datetime(bars["date"])[: len(labels)].dt.date
        
        # Filter labels for update range
        # Note: We might want to re-update slightly past labels if 5d target changes?
        # But kept simple: update labels for start_date onwards.
        # Labels for T-5 might become valid at T. 
        # If backfilling, we have future. If today, valid labels are null.
        # Ideally we process labels for all rows where we have data?
        # To be safe, we upsert labels for the new window.
        
        # Convert index to datetime for filtering
        labels_idx_dt = pd.to_datetime(labels.index)
        labels_to_upsert = labels[labels_idx_dt >= pd.to_datetime(start_date)]
        
        labels_to_upsert.index.name = "date"
        upsert_labels(db, asset_id_map[sym], labels_to_upsert)
        
        print(f"  ✅ Upserted {sym}: {len(features_json_df)} features, {len(labels_to_upsert)} labels")

    db.close()
    print("ETL complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, required=False, help="Start date (YYYY-MM-DD). If omitted, defaults to latest DB date + 1 day.")
    parser.add_argument("--end", type=str, required=False, help="End date (YYYY-MM-DD). If omitted, defaults to today.")
    parser.add_argument("--mode", type=str, choices=["backfill", "incremental"], default="incremental")
    args = parser.parse_args()

    # Default end to today if not provided
    if not args.end:
        args.end = date.today().isoformat()
    
    # Logic for start date handled inside run_etl if None
    run_etl(args.start, args.end, args.mode)
