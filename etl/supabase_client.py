import os
from typing import Optional, List, Dict, Any
import json
from supabase import create_client, Client

class SupabaseDB:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = url or os.getenv("SUPABASE_URL")

        # Prefer the service-role key. Once row-level security is enabled
        # (migration 017), the anon key is SELECT-only by design, so a pipeline
        # authenticating with it can read but silently writes nothing. The
        # fallback keeps existing setups running until the secret is added.
        self.key = key or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        self.using_service_key = bool(
            key is None and os.getenv("SUPABASE_SERVICE_KEY")
        )

        if not self.url or not self.key:
            raise ValueError(
                "Missing Supabase credentials. Set SUPABASE_URL and either "
                "SUPABASE_SERVICE_KEY (preferred, for writes) or SUPABASE_KEY."
            )

        if not self.using_service_key:
            print("  Note: using the anon key for writes. Set SUPABASE_SERVICE_KEY "
                  "before enabling RLS, or writes will start failing silently.")
        
        self.client: Client = create_client(self.url, self.key)
        self._asset_cache = None
        self._macro_cache = None
        self._columns_cache = {}

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

    # PostgREST / Postgres codes for "relation does not exist".
    MISSING_TABLE_CODES = frozenset({"42P01", "PGRST205"})
    # ... and for "column does not exist".
    MISSING_COLUMN_CODES = frozenset({"42703", "PGRST204"})

    def table_exists(self, table: str) -> bool:
        """
        Whether `table` exists, independent of whether it holds any rows.

        Necessary because available_columns() reads a sample row and therefore
        cannot tell an empty table from a missing one -- a freshly migrated
        table looks identical to one that was never created.
        """
        try:
            self.client.table(table).select("*").limit(1).execute()
            return True
        except Exception as exc:
            if any(code in str(exc) for code in self.MISSING_TABLE_CODES):
                return False
            raise

    def has_column(self, table: str, column: str) -> bool:
        """
        Whether `table` has `column`. Works on empty tables, since PostgREST
        validates the projection before it looks at any rows.
        """
        try:
            self.client.table(table).select(column).limit(1).execute()
            return True
        except Exception as exc:
            text = str(exc)
            if any(code in text for code in self.MISSING_COLUMN_CODES | self.MISSING_TABLE_CODES):
                return False
            raise

    def available_columns(self, table: str) -> set:
        """
        Column names present on a sample row of `table`, cached per process.

        Lets writers degrade gracefully when a migration has not been applied
        yet: a payload key the table does not have would otherwise fail the
        whole batch with PGRST204.

        An empty result means "unknown" -- the table is missing OR simply has no
        rows yet -- and callers treat that as "write everything and let the
        database object". Use table_exists() / has_column() to ask about schema.
        """
        if table not in self._columns_cache:
            try:
                resp = self.client.table(table).select("*").limit(1).execute()
                self._columns_cache[table] = set(resp.data[0].keys()) if resp.data else set()
            except Exception as exc:
                print(f"  Warning: could not introspect {table}: {exc}")
                self._columns_cache[table] = set()
        return self._columns_cache[table]

    def _filter_to_columns(self, table: str, rows):
        """Drop payload keys the table does not have, warning once per column."""
        cols = self.available_columns(table)
        if not cols:
            return rows
        unknown = {k for r in rows for k in r} - cols
        if unknown:
            print(f"  Note: {table} is missing {sorted(unknown)} - skipping those "
                  f"(apply the pending migration to store them)")
            return [{k: v for k, v in r.items() if k in cols} for r in rows]
        return rows

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

    def upsert_outcome_prices(self, rows):
        """
        Upsert outcome prices (future close prices) onto daily_bars.
        `rows` is a list of dicts already keyed by column name.
        """
        rows = self._filter_to_columns("daily_bars", rows)
        for i in range(0, len(rows), 1000):
            chunk = rows[i:i + 1000]
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
        Upsert label rows. `rows` is a list of dicts already keyed by column
        name (see etl.load_db.upsert_labels), so adding a horizon needs no
        change here.
        """
        rows = self._filter_to_columns("labels_daily", rows)
        for i in range(0, len(rows), 1000):
            chunk = rows[i:i + 1000]
            self.client.table("labels_daily").upsert(chunk, on_conflict="asset_id,date").execute()

    def get_latest_date(self) -> str:
        """Get the latest date present in the daily_bars table."""
        try:
            # Order by date desc, limit 1
            response = self.client.table("daily_bars") \
                .select("date") \
                .order("date", desc=True) \
                .limit(1) \
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]["date"]
            return None
        except Exception as e:
            print(f"Error fetching latest date: {e}")
            return None

    # Only OHLCV columns are safe to feed into feature computation.
    # Selecting "*" pulls DB metadata (id, created_at, source) and -- critically --
    # outcome_price_1d/5d/20d, which are FUTURE closes. Those flow through
    # compute_features straight into feature_json and leak the target.
    BAR_COLUMNS = "date, open, high, low, close, adj_close, volume"

    def fetch_daily_bars(self, asset_id: str, start_date: str) -> List[Dict]:
        """Fetch daily OHLCV bars for an asset from a specific start date."""
        try:
            response = self.client.table("daily_bars") \
                .select(self.BAR_COLUMNS) \
                .eq("asset_id", asset_id) \
                .gte("date", start_date) \
                .order("date", desc=False) \
                .execute()
            return response.data
        except Exception as e:
            print(f"Error fetching bars for {asset_id}: {e}")
            return []

    def fetch_macro_daily(self, series_id: str, start_date: str) -> List[Dict]:
        """Fetch macro data for a series from a specific start date."""
        try:
            response = self.client.table("macro_daily") \
                .select("date, value") \
                .eq("series_id", series_id) \
                .gte("date", start_date) \
                .order("date", desc=False) \
                .execute()
            return response.data
        except Exception as e:
            print(f"Error fetching macro for {series_id}: {e}")
            return []
