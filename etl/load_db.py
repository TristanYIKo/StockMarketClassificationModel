from typing import List, Dict
import json
import pandas as pd

from .supabase_client import SupabaseDB
from .transform_labels import HORIZONS


def upsert_asset_metadata(db: SupabaseDB, asset_rows: List[tuple]):
    """
    Upsert assets from list of tuples: (symbol, name, asset_type, exchange, currency)
    """
    db.upsert_assets(asset_rows)


def upsert_daily(db: SupabaseDB, asset_id: str, bars_df: pd.DataFrame):
    rows = []
    records = bars_df.to_dict('records')
    for record in records:
        open_val = float(record['open']) if pd.notna(record['open']) else None
        high_val = float(record['high']) if pd.notna(record['high']) else None
        low_val = float(record['low']) if pd.notna(record['low']) else None
        close_val = float(record['close']) if pd.notna(record['close']) else None
        adj_close_val = float(record['adj_close']) if pd.notna(record['adj_close']) else None
        volume_val = int(record['volume']) if pd.notna(record['volume']) else None
        
        rows.append((asset_id, record['date'], open_val, high_val, low_val, close_val, adj_close_val, volume_val, "yfinance"))
    
    if rows:
        db.upsert_daily_bars(rows)


def upsert_actions(db: SupabaseDB, asset_id: str, actions_df: pd.DataFrame):
    if actions_df.empty:
        return
    
    rows = []
    records = actions_df.to_dict('records')
    for record in records:
        dividend_val = float(record['dividend']) if 'dividend' in record and pd.notna(record['dividend']) else None
        split_val = float(record['split_ratio']) if 'split_ratio' in record and pd.notna(record['split_ratio']) else None
        
        rows.append((asset_id, record['date'], dividend_val, split_val, "yfinance"))
    
    if rows:
        db.upsert_corporate_actions(rows)


def upsert_features_json(db: SupabaseDB, asset_id: str, features_df: pd.DataFrame):
    """
    Upsert features as JSON.
    features_df should have columns: date, feature_json
    """
    rows = [
        (asset_id, r.date, json.dumps(r.feature_json) if isinstance(r.feature_json, dict) else r.feature_json)
        for r in features_df.itertuples(index=False)
    ]
    if rows:
        db.upsert_features_daily_json(rows)


def _num(row, attr):
    """Float value of `attr` on an itertuples row, or None if absent/NaN."""
    val = getattr(row, attr, None)
    return float(val) if val is not None and pd.notnull(val) else None


def _int(row, attr):
    """Int value of `attr` on an itertuples row, or None if absent/NaN."""
    val = getattr(row, attr, None)
    return int(val) if val is not None and pd.notnull(val) else None


def upsert_labels(db: SupabaseDB, asset_id: str, labels_df: pd.DataFrame):
    """
    Upsert classification labels for every horizon in HORIZONS.

    Primary targets are y_class_<h>d (binary: -1 DOWN, 1 UP). Diagnostic
    regression columns are kept alongside them.
    """
    rows = []
    for r in labels_df.itertuples():
        row = {
            "asset_id": asset_id,
            "date": str(r.Index),
            "primary_target": _num(r, "primary_target"),
            "y_thresh": _int(r, "y_thresh"),
        }
        for h in HORIZONS:
            row[f"y_class_{h}d"] = _int(r, f"y_class_{h}d")
            row[f"y_{h}d_raw"] = _num(r, f"y_{h}d_raw")
            row[f"y_{h}d_vol"] = _num(r, f"y_{h}d_vol")
            row[f"y_{h}d_clipped"] = _num(r, f"y_{h}d_clipped")
            row[f"y_{h}d_vol_clip"] = _num(r, f"y_{h}d_vol_clip")
            if h in (1, 5):  # legacy 0/1 columns
                row[f"y_{h}d"] = _int(r, f"y_{h}d")
        rows.append(row)

    if rows:
        db.upsert_labels_daily(rows)


def upsert_outcome_prices(db: SupabaseDB, asset_id: str, labels_df: pd.DataFrame):
    """
    Upsert outcome prices (future close prices) onto daily_bars.

    These are written so a prediction can be stored before its outcome is known,
    then resolved later once the future bar arrives. They are NOT features --
    see etl.transform_features_context.is_forbidden_feature.
    """
    rows = []
    for r in labels_df.itertuples():
        row = {"asset_id": asset_id, "date": str(r.Index)}
        for h in HORIZONS:
            row[f"outcome_price_{h}d"] = _num(r, f"outcome_price_{h}d")
        rows.append(row)

    if rows:
        db.upsert_outcome_prices(rows)


def upsert_macro_catalog(db: SupabaseDB, macro_series_dict: Dict[str, str]):
    """
    Upsert macro series catalog.
    macro_series_dict: {series_id: series_id} or {series_id: name}
    """
    # Note: this is updated in main.py to pass proper tuples
    pass  # Handled directly in main.py now


def upsert_macro_daily(db: SupabaseDB, series_id: str, df: pd.DataFrame):
    rows = [(series_id, r.date, float(r.value) if pd.notnull(r.value) else None) for r in df.itertuples(index=False)]
    if rows:
        db.upsert_macro_daily(rows)
