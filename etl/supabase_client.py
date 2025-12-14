import os
from typing import Optional, List, Dict, Any
import json
from supabase import create_client, Client

class SupabaseDB:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("Missing Supabase URL or KEY. Set SUPABASE_URL and SUPABASE_KEY environment variables.")
        
        self.client: Client = create_client(self.url, self.key)
        self._asset_cache = None
        self._macro_cache = None

    def close(self):
        pass  # Supabase client handles connection management

    def upsert_assets(self, rows):
        """Upsert assets. rows: list of (symbol, name, asset_type, exchange, currency)"""
        data = [
            {
                "symbol": row[0],
                "name": row[1],
                "asset_type": row[2],
                "exchange": row[3],
                "currency": row[4]
            }
            for row in rows
        ]
        for item in data:
            self.client.table("assets").upsert(item, on_conflict="symbol").execute()
        self._asset_cache = None  # Invalidate cache

    def get_asset_id_map(self):
        if self._asset_cache is None:
            response = self.client.table("assets").select("id, symbol").execute()
            self._asset_cache = {row["symbol"]: row["id"] for row in response.data}
        return self._asset_cache

    def upsert_daily_bars(self, rows):
        """Upsert daily bars. Batch process for performance."""
        data = [
            {
                "asset_id": row[0],
                "date": str(row[1]),
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "adj_close": row[6],
                "volume": row[7],
                "source": row[8]
            }
            for row in rows
        ]
        # Batch upsert in chunks of 1000
        for i in range(0, len(data), 1000):
            chunk = data[i:i+1000]
            self.client.table("daily_bars").upsert(chunk, on_conflict="asset_id,date").execute()

    def upsert_corporate_actions(self, rows):
        data = [
            {
                "asset_id": row[0],
                "date": str(row[1]),
                "dividend": row[2],
                "split_ratio": row[3],
                "source": row[4]
            }
            for row in rows
        ]
        for item in data:
            self.client.table("corporate_actions").upsert(item, on_conflict="asset_id,date").execute()

    def upsert_macro_series(self, rows):
        data = [
            {
                "series_key": row[0],
                "name": row[1],
                "frequency": row[2],
                "source": row[3]
            }
            for row in rows
        ]
        for item in data:
            self.client.table("macro_series").upsert(item, on_conflict="series_key").execute()
        self._macro_cache = None  # Invalidate cache

    def get_macro_series_id_map(self):
        if self._macro_cache is None:
            response = self.client.table("macro_series").select("id, series_key").execute()
            self._macro_cache = {row["series_key"]: row["id"] for row in response.data}
        return self._macro_cache

    def upsert_macro_daily(self, rows):
        data = [
            {
                "series_id": row[0],
                "date": str(row[1]),
                "value": row[2]
            }
            for row in rows
        ]
        # Batch upsert
        for i in range(0, len(data), 1000):
            chunk = data[i:i+1000]
            self.client.table("macro_daily").upsert(chunk, on_conflict="series_id,date").execute()

    def upsert_features_daily_json(self, rows):
        data = [
            {
                "asset_id": row[0],
                "date": str(row[1]),
                "feature_json": json.loads(row[2]) if isinstance(row[2], str) else row[2]
            }
            for row in rows
        ]
        # Batch upsert
        for i in range(0, len(data), 500):
            chunk = data[i:i+500]
            self.client.table("features_daily").upsert(chunk, on_conflict="asset_id,date").execute()

    def upsert_labels_daily(self, rows):
        """
        Upsert labels with regression and classification targets (v2.1 with triple-barrier).
        
        Row format: (asset_id, date, primary_target, y_1d_vol_clip, y_5d_vol_clip, y_class_1d, y_class_5d,
                     y_1d_raw, y_5d_raw, y_1d_vol, y_5d_vol, 
                     y_1d_clipped, y_5d_clipped, y_1d, y_5d, y_thresh)
        """
        data = [
            {
                "asset_id": row[0],
                "date": str(row[1]),
                # PRIMARY regression targets (vol-scaled + clipped)
                "primary_target": row[2],
                "y_1d_vol_clip": row[3],
                "y_5d_vol_clip": row[4],
                # CLASSIFICATION targets (triple-barrier)
                "y_class_1d": row[5],
                "y_class_5d": row[6],
                # Diagnostic regression targets
                "y_1d_raw": row[7],
                "y_5d_raw": row[8],
                "y_1d_vol": row[9],
                "y_5d_vol": row[10],
                "y_1d_clipped": row[11],
                "y_5d_clipped": row[12],
                # Binary classification targets (legacy)
                "y_1d": row[13],
                "y_5d": row[14],
                "y_thresh": row[15]
            }
            for row in rows
        ]
        # Batch upsert
        for i in range(0, len(data), 1000):
            chunk = data[i:i+1000]
            self.client.table("labels_daily").upsert(chunk, on_conflict="asset_id,date").execute()
