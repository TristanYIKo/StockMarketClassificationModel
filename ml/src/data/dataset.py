"""
Build the modeling dataset straight from Supabase.

Design notes
------------
* Features come from `features_daily.feature_json`, filtered through the same
  denylist the ETL writes with. Rows written before that denylist existed still
  carry `outcome_price_1d/5d` and DB bookkeeping columns, so filtering here is
  what actually keeps historical rows honest.
* Labels are NOT read from `labels_daily`. They are recomputed from the close
  series via `etl.transform_labels.compute_labels`. Labels are a pure function
  of prices, so deriving them at build time means a new horizon needs no
  migration and can never be stale relative to the bars.
* The result is cached to disk keyed by content, because pulling ~26k rows over
  PostgREST takes far longer than training does.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Dict, List, Optional

import pandas as pd

from etl.supabase_client import SupabaseDB
from etl.transform_features_context import is_forbidden_feature
from etl.transform_labels import compute_labels, HORIZONS

logger = logging.getLogger(__name__)

ETF_SYMBOLS = ("SPY", "QQQ", "DIA", "IWM")
PAGE = 1000

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "artifacts", "cache")


def _paginate(query_fn, label: str) -> List[Dict]:
    """Pull every row for a PostgREST query that caps at 1000 rows per call."""
    out: List[Dict] = []
    offset = 0
    while True:
        rows = query_fn(offset).execute().data
        if not rows:
            break
        out.extend(rows)
        offset += PAGE
        if len(rows) < PAGE:
            break
        if offset % 5000 == 0:
            logger.info("    %s: %d rows...", label, len(out))
    return out


def _fetch_features(db: SupabaseDB, asset_ids: Dict[str, str]) -> pd.DataFrame:
    """features_daily -> one row per (symbol, date) with feature columns unpacked."""
    frames = []
    for symbol, asset_id in asset_ids.items():
        rows = _paginate(
            lambda off, aid=asset_id: db.client.table("features_daily")
            .select("date, feature_json")
            .eq("asset_id", aid)
            .order("date")
            .range(off, off + PAGE - 1),
            f"features[{symbol}]",
        )
        if not rows:
            logger.warning("  no features for %s", symbol)
            continue

        parsed = [
            r["feature_json"] if isinstance(r["feature_json"], dict)
            else json.loads(r["feature_json"])
            for r in rows
        ]
        wide = pd.json_normalize(parsed)

        # The denylist is the load-bearing line in this file.
        drop = [c for c in wide.columns if is_forbidden_feature(c)]
        if drop:
            logger.info("  %s: dropped %d non-feature columns (%s)",
                        symbol, len(drop), ", ".join(sorted(drop)[:6]))
        wide = wide.drop(columns=drop)

        wide.insert(0, "date", pd.to_datetime([r["date"] for r in rows]))
        wide.insert(0, "symbol", symbol)
        frames.append(wide)
        logger.info("  %s: %d feature rows, %d features", symbol, len(wide), wide.shape[1] - 2)

    if not frames:
        raise RuntimeError("No feature rows returned from Supabase.")
    return pd.concat(frames, ignore_index=True)


def _fetch_closes(db: SupabaseDB, asset_ids: Dict[str, str]) -> pd.DataFrame:
    """daily_bars -> (symbol, date, close) for every ETF."""
    frames = []
    for symbol, asset_id in asset_ids.items():
        rows = _paginate(
            lambda off, aid=asset_id: db.client.table("daily_bars")
            .select("date, close")
            .eq("asset_id", aid)
            .order("date")
            .range(off, off + PAGE - 1),
            f"bars[{symbol}]",
        )
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["close"] = pd.to_numeric(df["close"])
        df["symbol"] = symbol
        frames.append(df.sort_values("date").reset_index(drop=True))
    return pd.concat(frames, ignore_index=True)


def _attach_labels(features: pd.DataFrame, closes: pd.DataFrame) -> pd.DataFrame:
    """Recompute every horizon's label per symbol and merge onto the features."""
    label_frames = []
    for symbol, grp in closes.groupby("symbol", sort=False):
        grp = grp.sort_values("date").reset_index(drop=True)

        # compute_labels needs vol_20 only for the diagnostic vol-scaled columns,
        # which the classifier never consumes; realised 20d std is fine here.
        vol_20 = grp["close"].pct_change().rolling(20).std().fillna(0.01)

        lab = compute_labels(grp["close"], vol_20)
        keep = ["close"] + [f"y_class_{h}d" for h in HORIZONS] + \
               [f"outcome_price_{h}d" for h in HORIZONS]
        lab = pd.concat([grp[["symbol", "date", "close"]], lab], axis=1)
        label_frames.append(lab[["symbol", "date"] + [c for c in keep]])

    labels = pd.concat(label_frames, ignore_index=True)
    merged = features.merge(labels, on=["symbol", "date"], how="inner")
    return merged.sort_values(["symbol", "date"]).reset_index(drop=True)


def _cache_key(symbols, max_date: str) -> str:
    raw = json.dumps({"symbols": sorted(symbols), "max_date": max_date})
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def build_dataset(
    symbols=ETF_SYMBOLS,
    use_cache: bool = True,
    db: Optional[SupabaseDB] = None,
) -> pd.DataFrame:
    """
    Return one DataFrame: symbol, date, <features...>, close, y_class_{1,5,20}d.

    Rows keep NULL labels at the tail (no future close yet); the trainer drops
    them per-horizon, so a 20d model loses 20 more rows than a 1d model rather
    than the whole frame losing 20.
    """
    db = db or SupabaseDB()
    asset_ids = {s: i for s, i in db.get_asset_id_map().items() if s in symbols}
    missing = set(symbols) - set(asset_ids)
    if missing:
        raise RuntimeError(f"Symbols not present in assets table: {sorted(missing)}")

    latest = db.client.table("daily_bars").select("date").order(
        "date", desc=True).limit(1).execute().data
    max_date = latest[0]["date"] if latest else "none"

    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"dataset_{_cache_key(symbols, max_date)}.pkl")
    if use_cache and os.path.exists(cache_path):
        logger.info("Loading cached dataset: %s", cache_path)
        return pd.read_pickle(cache_path)

    logger.info("Building dataset from Supabase (latest bar %s)...", max_date)
    features = _fetch_features(db, asset_ids)
    closes = _fetch_closes(db, asset_ids)
    df = _attach_labels(features, closes)

    logger.info("Dataset: %d rows x %d cols, %s to %s",
                len(df), df.shape[1], df["date"].min().date(), df["date"].max().date())
    for h in HORIZONS:
        n = df[f"y_class_{h}d"].notna().sum()
        logger.info("  y_class_%dd: %d labelled rows", h, n)

    df.to_pickle(cache_path)
    logger.info("Cached to %s", cache_path)
    return df
