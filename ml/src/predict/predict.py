"""
Generate and resolve predictions for every symbol and horizon.

    python -m ml.src.predict.predict --latest              # today's calls
    python -m ml.src.predict.predict --backfill 2025-01-01 # rebuild history
    python -m ml.src.predict.predict --resolve             # fill in outcomes
    ... --dry-run                                          # compute, write nothing

One model per day. Every call -- today's or a rebuilt historical one -- comes
from a model fit from scratch on the labels known by that day's close, used to
score that one day, and discarded (ml.src.train.train.fit_through). Nothing is
loaded from a pickle; the monthly retrain only chooses the algorithm and the
threshold, recorded in best_models.json.

  * --latest fits today's model and scores today.
  * --backfill replays the same thing for every past day. It reuses the
    per-day calls the retrain already computed (reports/<h>/walk_forward.csv)
    when they were made with the current algorithm and threshold, and fits
    any day not covered. Scoring the past with one recent model instead would
    be in-sample -- it trained on that past -- and the site's hit rate fiction.
  * --resolve scores nothing. It only writes outcomes onto calls already
    stored. It used to re-score the last 120 days with the current model, which
    silently rewrote recorded calls.

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

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from etl.supabase_client import SupabaseDB
from ml.src.data.dataset import build_dataset
from ml.src.data.features import to_stationary_features
from ml.src.models.direction import display_p_up
from ml.src.train.train import (DEFAULT_CONFIG, _quiet_preprocessor, fit_through,
                                load_config, walk_forward)

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


def session_index(calendar, first: pd.Timestamp, last: pd.Timestamp) -> pd.DatetimeIndex:
    """NYSE sessions from `first` through comfortably past `last` (for target dates)."""
    sched = calendar.schedule(start_date=first, end_date=last + pd.Timedelta(days=60))
    return pd.DatetimeIndex(sched.index).normalize()


def shape_rows(scored: pd.DataFrame, horizon: str, model_name: str,
               sessions: pd.DatetimeIndex) -> List[dict]:
    """
    Turn per-day scores into `predictions` rows.

    `scored` holds one row per (symbol, date) with `p_up_raw`, `threshold`,
    `close` and `outcome_price_<h>`. The stored p_up/p_down are the
    boundary-centred display values: argmax on them agrees with pred_class by
    construction, and ranking is unchanged.
    """
    h = HORIZON_DAYS[horizon]
    outcome_col = f"outcome_price_{horizon}"
    now = datetime.now(timezone.utc).isoformat()
    pos = {d: i for i, d in enumerate(sessions)}

    rows: List[dict] = []
    for r in scored.itertuples(index=False):
        r = r._asdict()
        as_of = pd.Timestamp(r["date"]).normalize()
        i = pos.get(as_of)
        if i is None or i + h >= len(sessions):
            logger.debug("  %s %s: target session not scheduled yet", r["symbol"], as_of.date())
            continue
        target = sessions[i + h]

        p_raw, t = float(r["p_up_raw"]), float(r["threshold"])
        p_up = float(display_p_up([p_raw], t)[0])
        p_down = 1.0 - p_up

        as_of_close = float(r["close"]) if pd.notna(r["close"]) else None
        outcome = r.get(outcome_col)
        outcome_close = float(outcome) if outcome is not None and pd.notna(outcome) else None
        actual_return = y_true = resolved_at = None
        if outcome_close is not None and as_of_close:
            actual_return = float(np.log(outcome_close / as_of_close))
            y_true = 1 if outcome_close > as_of_close else -1
            resolved_at = now

        rows.append({
            "symbol": r["symbol"],
            "horizon": horizon,
            "as_of_date": as_of.date().isoformat(),
            "target_date": target.date().isoformat(),
            "model_name": model_name,
            "split": "production",
            "pred_class": 1 if p_raw >= t else -1,
            "p_up": round(p_up, 6),
            "p_down": round(p_down, 6),
            "confidence": round(max(p_up, p_down), 6),
            "margin": round(abs(p_up - p_down), 6),
            "as_of_close": as_of_close,
            "outcome_close": outcome_close,
            "actual_return": actual_return,
            "y_true": y_true,
            "resolved_at": resolved_at,
            "updated_at": now,
        })
    return rows


def _attach_prices(scores: pd.DataFrame, df: pd.DataFrame, horizon: str) -> pd.DataFrame:
    """Join each day's score to that day's close and its (possibly pending) outcome."""
    cols = ["symbol", "date", "close", f"outcome_price_{horizon}"]
    s = scores.rename(columns={"as_of_date": "date"})[["symbol", "date", "p_up_raw", "threshold"]]
    s["date"] = pd.to_datetime(s["date"])
    return s.merge(df[cols], on=["symbol", "date"], how="inner")


def score_latest(df: pd.DataFrame, horizon: str, entry: dict, cfg: dict) -> pd.DataFrame:
    """Today's model: fit on labels known by the newest bar's close, score that bar."""
    latest = df["date"].max()
    name, t = entry["model_name"], float(entry["threshold"])
    model, pre, info = fit_through(df, horizon, name, t, cfg, latest)
    rows = df[df["date"] == latest]
    with _quiet_preprocessor():
        X = pre.transform(rows[pre.get_feature_names()])
    logger.info("%-4s %s fit on %d rows, labels through %s, scoring %s",
                horizon, name, info["rows"], info["labels_through"], latest.date())
    return pd.DataFrame({"symbol": rows["symbol"].values, "as_of_date": latest,
                         "p_up_raw": model.predict_proba(X)[:, 1], "threshold": t})


def backfill_scores(df: pd.DataFrame, horizon: str, entry: dict, cfg: dict,
                    since: str) -> pd.DataFrame:
    """
    Per-day walk-forward scores for every session from `since`.

    Reuses reports/<h>/walk_forward.csv for days it covers, but only when it was
    produced by the algorithm and threshold now selected -- otherwise those
    calls belong to a different model. Every other day is fit fresh.
    """
    name, t = entry["model_name"], float(entry["threshold"])
    since = pd.Timestamp(since)
    days = pd.DatetimeIndex(np.sort(df.loc[df["date"] >= since, "date"].unique()))
    if days.empty:
        return pd.DataFrame()

    cached = pd.DataFrame()
    path = os.path.join(ARTIFACTS, "reports", horizon, "walk_forward.csv")
    if os.path.exists(path):
        c = pd.read_csv(path, parse_dates=["as_of_date"])
        ok = (c["model_name"] == name) & np.isclose(c["threshold"], t)
        cached = c[ok & c["as_of_date"].isin(days)]
        if (~ok).any():
            logger.info("     %s: ignoring %d cached rows from a different model/threshold",
                        horizon, int((~ok).sum()))

    covered = set(cached["as_of_date"]) if not cached.empty else set()
    todo = [d for d in days if d not in covered]
    logger.info("     %s: %d days from cache, %d to fit fresh", horizon, len(covered), len(todo))

    parts = [cached[["symbol", "as_of_date", "p_up_raw", "threshold"]]] if not cached.empty else []
    if todo:
        # Contiguous tail in practice (days after the last retrain); fit each one.
        fresh = walk_forward(df, horizon, name, t, cfg, start=min(todo))
        if not fresh.empty:
            fresh = fresh[fresh["as_of_date"].isin(todo)]
            parts.append(fresh[["symbol", "as_of_date", "p_up_raw", "threshold"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


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


def fetch_unresolved(db: SupabaseDB, horizons: List[str]) -> List[dict]:
    """Stored production calls that do not have an outcome yet."""
    out: List[dict] = []
    page, start = 1000, 0
    while True:
        resp = (db.client.table(TABLE)
                .select("symbol,horizon,as_of_date,model_name,as_of_close")
                .eq("split", "production")
                .is_("y_true", "null")
                .in_("horizon", horizons)
                .order("as_of_date")
                .range(start, start + page - 1)
                .execute())
        batch = resp.data or []
        out.extend(batch)
        if len(batch) < page:
            return out
        start += page


def resolve_outcomes(db: SupabaseDB, df: pd.DataFrame, horizons: List[str],
                     dry_run: bool) -> int:
    """
    Write outcomes onto stored calls whose target session has closed.

    Touches only the outcome columns, by row key. The call itself -- pred_class,
    p_up, model_name -- is what the system said at the time, and resolution
    must never change it.
    """
    pending = fetch_unresolved(db, horizons)
    lookup = df.set_index(["symbol", "date"]).sort_index()
    now = datetime.now(timezone.utc).isoformat()

    done = 0
    for r in pending:
        key = (r["symbol"], pd.Timestamp(r["as_of_date"]))
        if key not in lookup.index:
            continue
        outcome = lookup.loc[key, f"outcome_price_{r['horizon']}"]
        if pd.isna(outcome):
            continue  # target session has not closed yet
        as_of_close = r.get("as_of_close")
        as_of_close = float(as_of_close) if as_of_close is not None else float(lookup.loc[key, "close"])
        outcome = float(outcome)
        if not (np.isfinite(as_of_close) and np.isfinite(outcome)) or as_of_close <= 0:
            # A bar stored without a close (see etl.extract_yf.drop_incomplete_bars).
            # NaN compares False, so this would otherwise be recorded as DOWN.
            continue

        fields = {
            "outcome_close": outcome,
            "actual_return": float(np.log(outcome / as_of_close)),
            "y_true": 1 if outcome > as_of_close else -1,
            "resolved_at": now,
            "updated_at": now,
        }
        if not dry_run:
            (db.client.table(TABLE).update(fields)
             .eq("symbol", r["symbol"]).eq("horizon", r["horizon"])
             .eq("as_of_date", r["as_of_date"]).eq("model_name", r["model_name"])
             .eq("split", "production")
             .execute())
        done += 1

    logger.info("Resolved %d of %d pending calls%s", done, len(pending),
                " (dry run, nothing written)" if dry_run else "")
    return done


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
                    help="Only write outcomes onto already-stored predictions")
    ap.add_argument("--horizons", default="1d,5d,20d")
    ap.add_argument("--no-cache", action="store_true", help="Re-pull the dataset")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute everything, write nothing to Supabase")
    args = ap.parse_args()

    if not (args.latest or args.backfill or args.resolve):
        args.latest = True

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.dry_run:
        logger.info("DRY RUN: nothing will be written to Supabase.")

    db = SupabaseDB()
    ensure_table(db)

    pointer = load_pointer()
    calendar = mcal.get_calendar("NYSE")
    horizons = [h.strip() for h in args.horizons.split(",")]

    df = build_dataset(use_cache=not args.no_cache)
    df, _ = to_stationary_features(df)

    total = 0
    if args.latest or args.backfill:
        cfg = load_config(DEFAULT_CONFIG)
        first = pd.Timestamp(args.backfill) if args.backfill else df["date"].max()
        sessions = session_index(calendar, first, df["date"].max())
        for horizon in horizons:
            if horizon not in pointer:
                raise KeyError(f"No model selected for {horizon}. Train first.")
            entry = pointer[horizon]
            model_name = entry["model_name"]
            scores = (backfill_scores(df, horizon, entry, cfg, args.backfill)
                      if args.backfill else score_latest(df, horizon, entry, cfg))
            rows = (shape_rows(_attach_prices(scores, df, horizon), horizon,
                               model_name, sessions) if not scores.empty else [])

            if args.dry_run:
                n = len(rows)
            else:
                n = upsert(db, rows)
                retire_superseded(db, horizon, model_name)
            resolved = sum(1 for r in rows if r["y_true"] is not None)
            logger.info("%-4s %-22s %s %4d rows (%d resolved, %d pending)",
                        horizon, model_name, "would write" if args.dry_run else "wrote",
                        n, resolved, n - resolved)
            if not args.backfill:
                for r in rows:
                    logger.info("     %s  as_of %s -> target %s  %s  p_up=%.3f",
                                r["symbol"], r["as_of_date"], r["target_date"],
                                "UP  " if r["pred_class"] == 1 else "DOWN", r["p_up"])
            total += n
        logger.info("Done: %d prediction rows %s.", total,
                    "computed" if args.dry_run else "upserted")

    if args.resolve:
        resolve_outcomes(db, df, horizons, args.dry_run)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
