"""
Generate and resolve predictions for every symbol and horizon.

    python -m ml.src.predict.predict --latest              # today's calls
    python -m ml.src.predict.predict --backfill 2025-01-01 # rebuild history
    python -m ml.src.predict.predict --resolve             # fill in outcomes

Replaces generate_real_predictions.py, which had three defects:

  1. It stored every horizon's prediction on the *next* trading day, so a 5d
     prediction claimed to be about tomorrow rather than five sessions out.
  2. It wrote the target day into `date`, while training wrote the feature day
     into the same column, so the website scored production rows against the
     wrong day's return.
  3. It rebuilt the inference feature vector by hand from feature_json, which
     did not match the transforms training applied.

Here, features come from exactly the same build_dataset + to_stationary_features
path the trainer uses, and every row records as_of_date and target_date
separately. Outcomes come from outcome_price_<h>d, which the dataset already
computes, so a backfilled prediction is resolved the moment its future bar
exists.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from etl.supabase_client import SupabaseDB
from ml.src.data.dataset import build_dataset
from ml.src.data.features import to_stationary_features

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARTIFACTS = os.path.join(ROOT, "artifacts")
MODELS_DIR = os.path.join(ARTIFACTS, "models")
POINTER = os.path.join(MODELS_DIR, "best_models.json")

HORIZON_DAYS = {"1d": 1, "5d": 5, "20d": 20}
TABLE = "predictions"


def load_pointer() -> Dict[str, dict]:
    if not os.path.exists(POINTER):
        raise FileNotFoundError(
            f"{POINTER} not found. Train first: python -m ml.src.train.train --all")
    with open(POINTER, encoding="utf-8") as fh:
        return json.load(fh)


def load_artifacts(horizon: str, pointer: Dict[str, dict]):
    """Return (model, preprocessor, algorithm_name) for a horizon."""
    if horizon not in pointer:
        raise KeyError(f"No trained model recorded for horizon {horizon}")
    entry = pointer[horizon]
    d = os.path.join(MODELS_DIR, entry["artifact_dir"])
    model = joblib.load(os.path.join(d, "model.pkl"))
    pre = joblib.load(os.path.join(d, "preprocessor.pkl"))
    return model, pre, entry["model_name"]


def trading_day_offset(calendar, start: pd.Timestamp, n: int) -> Optional[pd.Timestamp]:
    """The NYSE session n trading days after `start`, or None if not scheduled yet."""
    sched = calendar.schedule(start_date=start,
                              end_date=start + pd.Timedelta(days=n * 3 + 20))
    idx = sched.index
    if len(idx) <= n:
        return None
    return idx[n]


def build_rows(df: pd.DataFrame, horizon: str, model, pre, model_name: str,
               calendar, since: Optional[str], latest_only: bool) -> List[dict]:
    """Score `df` for one horizon and shape it into `predictions` rows."""
    h = HORIZON_DAYS[horizon]
    feats = list(pre.get_feature_names())

    work = df.copy()
    if since:
        work = work[work["date"] >= pd.to_datetime(since)]
    if latest_only:
        work = work.sort_values("date").groupby("symbol", as_index=False).tail(1)
    if work.empty:
        return []

    missing = [c for c in feats if c not in work.columns]
    if missing:
        raise RuntimeError(f"Inference frame is missing trained features: {missing[:8]}")

    X = pre.transform(work[feats])
    pred = model.predict(X)

    # Store the boundary-centred probabilities: these are what the dashboard
    # renders, and argmax on them agrees with `pred` by construction. Ranking is
    # identical to the raw output, so stored confidence stays comparable across
    # horizons even though each has its own tuned threshold.
    proba = (model.predict_proba_display(X)
             if hasattr(model, "predict_proba_display")
             else model.predict_proba(X))
    p_down, p_up = proba[:, 0], proba[:, 1]
    outcome_col = f"outcome_price_{horizon}"

    rows: List[dict] = []
    for i, (_, r) in enumerate(work.iterrows()):
        as_of = pd.Timestamp(r["date"])
        target = trading_day_offset(calendar, as_of, h)
        if target is None:
            logger.debug("  %s %s: target session not scheduled yet", r["symbol"], as_of.date())
            continue

        as_of_close = float(r["close"]) if pd.notna(r["close"]) else None
        outcome = r.get(outcome_col)
        outcome_close = float(outcome) if pd.notna(outcome) else None

        actual_return = y_true = resolved_at = None
        if outcome_close is not None and as_of_close:
            actual_return = float(np.log(outcome_close / as_of_close))
            y_true = 1 if outcome_close > as_of_close else -1
            resolved_at = datetime.now(timezone.utc).isoformat()

        rows.append({
            "symbol": r["symbol"],
            "horizon": horizon,
            "as_of_date": as_of.date().isoformat(),
            "target_date": target.date().isoformat(),
            "model_name": model_name,
            "split": "production",
            "pred_class": int(pred[i]),
            "p_up": round(float(p_up[i]), 6),
            "p_down": round(float(p_down[i]), 6),
            "confidence": round(float(max(p_up[i], p_down[i])), 6),
            "margin": round(float(abs(p_up[i] - p_down[i])), 6),
            "as_of_close": as_of_close,
            "outcome_close": outcome_close,
            "actual_return": actual_return,
            "y_true": y_true,
            "resolved_at": resolved_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    return rows


def upsert(db: SupabaseDB, rows: List[dict]) -> int:
    """Upsert on the natural key so re-runs refresh rather than duplicate."""
    if not rows:
        return 0
    for i in range(0, len(rows), 500):
        db.client.table(TABLE).upsert(
            rows[i:i + 500],
            on_conflict="symbol,horizon,as_of_date,model_name,split",
        ).execute()
    return len(rows)


def retire_superseded(db: SupabaseDB, horizon: str, model_name: str) -> int:
    """
    Delete production rows for this horizon produced by any OTHER model.

    The table's unique key includes model_name, so when a retrain changes which
    algorithm wins a horizon, the new rows are INSERTED alongside the old ones
    rather than replacing them. Two rows then exist for the same day and
    horizon, and the dashboard -- which takes the newest row per horizon -- picks
    between them arbitrarily. That is how a stale logistic_regression call for
    20d outlived the xgboost model that had superseded it.

    Conceptually there is exactly one production prediction per (symbol,
    horizon, as_of_date); the model that produced it is an attribute of that
    row, not part of its identity. This enforces that.
    """
    resp = (db.client.table(TABLE)
            .delete()
            .eq("horizon", horizon)
            .eq("split", "production")
            .neq("model_name", model_name)
            .execute())
    n = len(resp.data or [])
    if n:
        logger.info("     retired %d row(s) from a superseded model for %s", n, horizon)
    return n


def ensure_table(db: SupabaseDB):
    # table_exists, not available_columns: the latter samples a row, so a
    # newly-migrated empty table would look missing.
    if not db.table_exists(TABLE):
        raise SystemExit(
            "\nThe `predictions` table does not exist yet.\n"
            "Apply migrations/016_add_20d_horizon_and_predictions.sql in the\n"
            "Supabase SQL editor, then re-run this command.\n")


def main():
    ap = argparse.ArgumentParser(description="Generate model predictions")
    ap.add_argument("--latest", action="store_true",
                    help="Predict only the most recent session per symbol")
    ap.add_argument("--backfill", metavar="YYYY-MM-DD",
                    help="Rebuild predictions for every session from this date on")
    ap.add_argument("--resolve", action="store_true",
                    help="Only refresh outcomes for already-stored predictions")
    ap.add_argument("--horizons", default="1d,5d,20d")
    ap.add_argument("--no-cache", action="store_true", help="Re-pull the dataset")
    args = ap.parse_args()

    if not (args.latest or args.backfill or args.resolve):
        args.latest = True

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    db = SupabaseDB()
    ensure_table(db)

    pointer = load_pointer()
    calendar = mcal.get_calendar("NYSE")

    df = build_dataset(use_cache=not args.no_cache)
    df, _ = to_stationary_features(df)

    # --resolve re-scores the same window so outcomes that have since landed get
    # written back; upsert makes that idempotent.
    since = args.backfill
    latest_only = args.latest and not args.backfill and not args.resolve
    if args.resolve and not since:
        since = (pd.Timestamp.today() - pd.Timedelta(days=120)).date().isoformat()

    total = 0
    for horizon in [h.strip() for h in args.horizons.split(",")]:
        model, pre, model_name = load_artifacts(horizon, pointer)
        rows = build_rows(df, horizon, model, pre, model_name,
                          calendar, since, latest_only)
        n = upsert(db, rows)
        retire_superseded(db, horizon, model_name)
        resolved = sum(1 for r in rows if r["y_true"] is not None)
        logger.info("%-4s %-22s wrote %4d rows (%d resolved, %d pending)",
                    horizon, model_name, n, resolved, n - resolved)
        if latest_only:
            for r in rows:
                logger.info("     %s  as_of %s -> target %s  %s  p_up=%.3f",
                            r["symbol"], r["as_of_date"], r["target_date"],
                            "UP  " if r["pred_class"] == 1 else "DOWN", r["p_up"])
        total += n

    logger.info("Done: %d prediction rows upserted.", total)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
