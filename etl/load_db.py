from typing import List, Dict
import json
import pandas as pd

from .supabase_client import SupabaseDB


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


def upsert_labels(db: SupabaseDB, asset_id: str, labels_df: pd.DataFrame):
    """
    Upsert classification labels.
    
    PRIMARY: y_class_1d (triple-barrier classification: -1, 0, 1)
    Diagnostic columns kept for backwards compatibility but not used in modeling.
    """
    rows = []
    for r in labels_df.itertuples():
        row = (
            asset_id,
            r.Index,  # date
            # PRIMARY TARGETS (vol-scaled + clipped)
            float(r.primary_target) if hasattr(r, 'primary_target') and pd.notnull(r.primary_target) else None,
            float(r.y_1d_vol_clip) if hasattr(r, 'y_1d_vol_clip') and pd.notnull(r.y_1d_vol_clip) else None,
            float(r.y_5d_vol_clip) if hasattr(r, 'y_5d_vol_clip') and pd.notnull(r.y_5d_vol_clip) else None,
            # CLASSIFICATION TARGET (triple-barrier)
            int(r.y_class_1d) if hasattr(r, 'y_class_1d') and pd.notnull(r.y_class_1d) else None,
            # Diagnostic regression targets
            float(r.y_1d_raw) if hasattr(r, 'y_1d_raw') and pd.notnull(r.y_1d_raw) else None,
            float(r.y_5d_raw) if hasattr(r, 'y_5d_raw') and pd.notnull(r.y_5d_raw) else None,
            float(r.y_1d_vol) if hasattr(r, 'y_1d_vol') and pd.notnull(r.y_1d_vol) else None,
            float(r.y_5d_vol) if hasattr(r, 'y_5d_vol') and pd.notnull(r.y_5d_vol) else None,
            float(r.y_1d_clipped) if hasattr(r, 'y_1d_clipped') and pd.notnull(r.y_1d_clipped) else None,
            float(r.y_5d_clipped) if hasattr(r, 'y_5d_clipped') and pd.notnull(r.y_5d_clipped) else None,
            # Binary classification targets (legacy)
            int(r.y_1d) if pd.notnull(r.y_1d) else None,
            int(r.y_5d) if pd.notnull(r.y_5d) else None,
            int(r.y_thresh) if pd.notnull(r.y_thresh) else None,
        )
        rows.append(row)
    
    if rows:
        db.upsert_labels_daily(rows)


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
