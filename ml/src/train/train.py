"""
Train direction classifiers for one horizon.

    python -m ml.src.train.train --horizon 1d
    python -m ml.src.train.train --horizon 5d
    python -m ml.src.train.train --horizon 20d
    python -m ml.src.train.train --all

Replaces train_models_1d.py / train_models_5d.py, which monkey-patched module
globals to switch targets and could only ever read a committed CSV snapshot.
Data comes from Supabase via ml.src.data.dataset, so a retrain always sees
whatever the ETL loaded last.

Every model is fit on internal labels 0 = DOWN, 1 = UP and wrapped in
DirectionModel, which restores the external -1/1 convention and guarantees
predict_proba returns [p_down, p_up].

Two different fits come out of a run, and they answer different questions:

  * The candidate models are fit on the fixed train window and judged on the
    fixed validation window. That is how an algorithm and a threshold get
    chosen, and the frozen test scores in the report come from these fits.
  * The selected algorithm is never served frozen. Every day it is refit from
    scratch on the labels known by that day's close (fit_through), scores that
    one day, and is discarded. Without this the splits pin training to 2023
    (2021 at 20d), so a "monthly retrain" would refit the same old window
    forever and never see a recent market.

The report scores the selected model walk-forward over the test period with
that same one-model-per-day procedure (walk_forward), because that, not the
frozen fit, is the process the site is actually serving.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score,
                             log_loss, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import lightgbm as lgb
import xgboost as xgb

from ml.src.data.dataset import build_dataset
from ml.src.models.direction import DirectionModel
from ml.src.data.features import to_stationary_features
from ml.src.utils.preprocess import TimeSeriesPreprocessor

logger = logging.getLogger(__name__)

HORIZONS = ("1d", "5d", "20d")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARTIFACTS = os.path.join(ROOT, "artifacts")
DEFAULT_CONFIG = os.path.join(ROOT, "config", "model_config.yaml")

# Never features: identifiers, the price denominator, and every label/outcome.
NON_FEATURES = {"symbol", "date", "close"}


HORIZON_DAYS = {"1d": 1, "5d": 5, "20d": 20}


def horizon_splits(cfg: dict, horizon_days: int, data: pd.DataFrame) -> dict:
    """
    Split dates for ONE horizon. Validation is sized in events, not calendar days.

    A single validation year holds ~252 sessions. That is ~250 independent 1d
    events, but only ~50 non-overlapping 5d windows and ~12 non-overlapping 20d
    windows. Selecting a model and a threshold on twelve events is noise: at 20d
    the winner on validation AUC (0.618) scored 0.449 on test -- worse than
    chance -- purely from picking the luckiest of four candidates.

    So the validation window grows with the horizon, holding roughly
    MIN_VAL_EVENTS non-overlapping windows at every horizon. Longer horizons buy
    that coverage out of training history, which is the correct trade: a 20d
    model has ~320 independent events in 25 years no matter how the data is
    sliced, and spending some on honest evaluation beats fitting more of them.

    Test is left untouched and identical across horizons, so the three models
    stay comparable on the same out-of-sample period.
    """
    MIN_VAL_EVENTS = 40
    SESSIONS_PER_YEAR = 252

    s = cfg["splits"]
    val_end = pd.to_datetime(s["val_end"])
    needed_sessions = max(SESSIONS_PER_YEAR, MIN_VAL_EVENTS * horizon_days)

    # Walk back `needed_sessions` trading days from val_end through the dates
    # actually present, so the window reflects real sessions not calendar days.
    dates = np.sort(data["date"].unique())
    upto = dates[dates <= val_end]
    val_start = pd.Timestamp(upto[-min(needed_sessions, len(upto))])

    return {
        "train_start": pd.to_datetime(s["train_start"]),
        "train_end": val_start - pd.Timedelta(days=1),
        "val_start": val_start,
        "val_end": val_end,
        "test_start": pd.to_datetime(s["test_start"]),
        "test_end": pd.to_datetime(s["test_end"]),
        "val_sessions": needed_sessions,
    }


def purge_boundary(split: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    """
    Drop the tail of a split whose labels resolve after the split ends.

    A 20d label stamped 2023-12-15 is decided by the close on ~2024-01-16, which
    lives in the validation window. Training on it leaks the future: 80 rows per
    split boundary at the 20d horizon, 20 at 5d, 4 at 1d. Removing the last
    `horizon_days` observations per symbol makes each split self-contained --
    the standard purge from combinatorial cross-validation, applied here to a
    simple chronological split.

    This is horizon-specific by construction: the 1d model gives up 4 rows, the
    20d model 80.
    """
    if horizon_days <= 0 or split.empty:
        return split
    tail_idx = split.sort_values("date").groupby("symbol").tail(horizon_days).index
    return split.drop(index=tail_idx)


def effective_n(split: pd.DataFrame, horizon_days: int) -> int:
    """
    Number of genuinely independent observations in a split.

    Two things shrink it, and both are horizon-dependent:

    1. **Overlapping windows.** Consecutive h-day labels share h-1 of their h
       days, so ~h consecutive rows describe one event. Dividing the number of
       distinct dates by h approximates the count of non-overlapping windows.

    2. **Cross-sectional correlation.** SPY, QQQ, DIA and IWM move together;
       four rows on the same date are close to one observation, not four. Using
       distinct dates rather than row count already collapses them.

    At the 20d horizon this takes 25,748 rows down to ~320 events. Treating the
    row count as the sample size overstates precision ~80x and is what let the
    threshold search chase noise.
    """
    dates = split["date"].nunique()
    return max(1, dates // max(horizon_days, 1))


def _balanced_accuracy_se(y_true, pred, n_eff: int) -> float:
    """
    Standard error of balanced accuracy = (TPR + TNR) / 2, on EFFECTIVE sample
    size rather than row count.

    TPR and TNR are binomial proportions, so Var(bal) = (Var(TPR) + Var(TNR))/4.
    The effective count is split between the classes in the observed proportion.
    """
    y_true = np.asarray(y_true)
    pred = np.asarray(pred)
    pos = y_true == 1
    neg = ~pos
    if pos.sum() == 0 or neg.sum() == 0:
        return float("inf")

    # Apportion the effective sample between classes at the observed base rate.
    base = float(pos.mean())
    n_pos = max(1.0, n_eff * base)
    n_neg = max(1.0, n_eff * (1 - base))

    tpr = float((pred[pos] == 1).mean())
    tnr = float((pred[neg] == -1).mean())
    var = (tpr * (1 - tpr) / n_pos + tnr * (1 - tnr) / n_neg) / 4.0

    # A degenerate rule (TPR=1, TNR=0) has zero binomial variance, which would
    # claim infinite precision for the least informative threshold there is.
    # Floor the estimate at the SE of a coin flip on the same effective sample.
    floor = 0.5 / np.sqrt(max(n_eff, 1))
    return float(max(np.sqrt(var), floor))


def tune_threshold(model: "DirectionModel", X_val, y_val, n_eff: int) -> float:
    """
    Pick the p_up cutoff on validation: balanced accuracy, one-standard-error
    rule, ties broken toward this horizon's own base rate.

    Three failure modes, in the order they were hit:

    1. Optimising RAW accuracy collapses onto the majority class. Up-rates rise
       with horizon (0.54 at 1d, 0.57 at 5d, 0.62 at 20d), so "always UP" gets
       progressively harder to beat and the optimiser simply took it -- the 1d
       model called UP on 99.4% of days.

    2. Taking the single best balanced-accuracy threshold overfits validation.

    3. Sizing the error bar by ROW COUNT pretends 20d has 25k independent
       observations when overlapping windows and four correlated ETFs leave
       ~320. The band was ~9x too tight, so (2) came back through the side door.

    `n_eff` must therefore come from effective_n() for this horizon. Among
    thresholds statistically tied with the peak, the one whose predicted UP-rate
    is closest to the observed base rate is chosen: the most stable member of
    the tied set, and non-degenerate whenever the base rate is.
    """
    p_up = model.predict_proba(X_val)[:, 1]
    y = np.asarray(y_val)
    grid = np.round(np.arange(0.05, 0.9501, 0.005), 4)

    scored = []
    for t in grid:
        pred = np.where(p_up >= t, 1, -1)
        scored.append((balanced_accuracy_score(y, pred), float(t), pred))

    best_bal, best_t_raw, best_pred = max(scored, key=lambda r: r[0])
    se = _balanced_accuracy_se(y, best_pred, n_eff)
    base_rate = float((y == 1).mean())

    if best_bal <= 0.5 + 1e-9:
        # No threshold separates the classes at all, so there is nothing to
        # tune. Match the base rate rather than letting argmax settle on the
        # degenerate all-one-class rule that also scores exactly 0.50.
        _, chosen_bal, chosen_t = min(
            ((abs((pred == 1).mean() - base_rate), bal, t) for bal, t, pred in scored),
            key=lambda r: r[0])
        logger.info("  threshold %.3f | NO DISCRIMINATION on val (peak bal-acc %.4f); "
                    "matched to base rate %.1f%%", chosen_t, best_bal, 100 * base_rate)
        return chosen_t

    within = [(abs((pred == 1).mean() - base_rate), bal, t)
              for bal, t, pred in scored if bal >= best_bal - se]
    _, chosen_bal, chosen_t = min(within, key=lambda r: r[0])

    pred = np.where(p_up >= chosen_t, 1, -1)
    logger.info("  threshold %.3f | bal-acc %.4f (peak %.4f @ %.3f) | n_eff=%d "
                "1se=%.4f (%d tied) | calls UP %.1f%% vs base rate %.1f%%",
                chosen_t, chosen_bal, best_bal, best_t_raw, n_eff, se, len(within),
                100 * (pred == 1).mean(), 100 * base_rate)
    return chosen_t


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def feature_columns(df: pd.DataFrame) -> List[str]:
    """Everything that is not an identifier, a label, or an outcome price."""
    return [
        c for c in df.columns
        if c not in NON_FEATURES
        and not c.startswith(("y_class_", "outcome_price_", "y_1d", "y_5d", "y_20d"))
    ]


def baselines(y_train: pd.Series, y_eval: pd.Series) -> Dict[str, float]:
    """
    Honest reference points for a binary direction task.

    majority_class is what you get predicting the training set's more common
    class every day, which is the number any model must beat to have shown
    anything at all.
    """
    maj = 1 if (y_train == 1).mean() >= 0.5 else -1
    return {
        "always_up": float((y_eval == 1).mean()),
        "majority_class": float((y_eval == maj).mean()),
        "majority_label": float(maj),
        "eval_up_rate": float((y_eval == 1).mean()),
    }


def evaluate(model: DirectionModel, X, y, split: str, y_train: pd.Series) -> Dict:
    proba = model.predict_proba(X)
    pred = model.predict(X)
    p_up = proba[:, 1]
    y_bin = (y == 1).astype(int)

    base = baselines(y_train, y)
    acc = accuracy_score(y, pred)

    metrics = {
        "split": split,
        "n": int(len(y)),
        "accuracy": float(acc),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "f1_macro": float(f1_score(y, pred, average="macro", labels=[-1, 1], zero_division=0)),
        "roc_auc": float(roc_auc_score(y_bin, p_up)) if y_bin.nunique() > 1 else float("nan"),
        "log_loss": float(log_loss(y_bin, np.clip(p_up, 1e-6, 1 - 1e-6))),
        "brier": float(brier_score_loss(y_bin, p_up)),
        "up_rate_pred": float((pred == 1).mean()),
        "threshold": float(model.threshold),
        **base,
        "edge_vs_majority": float(acc - base["majority_class"]),
    }
    cm = confusion_matrix(y, pred, labels=[-1, 1])
    metrics["confusion_matrix"] = cm.tolist()
    return metrics


def build_estimator(name: str, cfg: dict):
    params = dict(cfg["models"][name].get("params", {}))
    if name == "logistic_regression":
        return Pipeline([("scale", StandardScaler()),
                         ("clf", LogisticRegression(**params))])
    if name == "random_forest":
        return RandomForestClassifier(**params)
    if name == "lightgbm":
        return lgb.LGBMClassifier(class_weight="balanced", **params)
    if name == "xgboost":
        return xgb.XGBClassifier(**params)
    raise ValueError(f"Unknown model: {name}")


def fit_estimator(name: str, cfg: dict, X, y_int):
    """Build and fit one learner on internal 0/1 labels."""
    est = build_estimator(name, cfg)
    if name == "xgboost":
        # XGBClassifier has no class_weight; this is its "balanced" equivalent.
        # It must come from the rows THIS fit sees, so a refit on a different
        # window gets its own weight rather than inheriting a stale one.
        pos_weight = float((y_int == 0).sum() / max((y_int == 1).sum(), 1))
        est.set_params(scale_pos_weight=pos_weight)
    est.fit(X, y_int)
    return est


def make_preprocessor(cfg: dict) -> TimeSeriesPreprocessor:
    return TimeSeriesPreprocessor(
        drop_features_threshold=cfg["preprocessing"]["missing_threshold"],
        imputation_strategy=cfg["preprocessing"]["imputation_strategy"],
        scaling=False,
    )


@contextmanager
def _quiet_preprocessor():
    """The preprocessor logs a page per fit; a walk-forward does dozens of fits."""
    lg = logging.getLogger("ml.src.utils.preprocess")
    old = lg.level
    lg.setLevel(logging.WARNING)
    try:
        yield
    finally:
        lg.setLevel(old)


def last_trainable_date(dates: np.ndarray, cutoff, horizon_days: int) -> Optional[pd.Timestamp]:
    """
    The newest as-of date whose h-session label was already decided at `cutoff`.

    A row's label is the close `horizon_days` sessions later, so at the close of
    `cutoff` only rows at least that many sessions older have a known answer.
    Training on anything newer would be fitting to a future the model could
    not have seen when it was fit -- the same leak purge_boundary() closes
    between splits, applied to a moving cutoff.
    """
    known = dates[dates <= np.datetime64(pd.Timestamp(cutoff))]
    if len(known) <= horizon_days:
        return None
    return pd.Timestamp(known[-1 - horizon_days])


def fit_through(df: pd.DataFrame, horizon: str, name: str, threshold: float,
                cfg: dict, cutoff) -> Tuple[DirectionModel, TimeSeriesPreprocessor, dict]:
    """
    Refit an already-selected model on every label known at `cutoff`.

    Only the training window moves. The algorithm and the decision threshold
    were settled on the fixed validation window and are deliberately not
    revisited: re-tuning them on the newest data would leave nothing held out
    to judge them on.

    `df` is the full dataset, labelled and unlabelled rows alike; the session
    calendar comes from its dates.
    """
    target = f"y_class_{horizon}"
    h_days = HORIZON_DAYS[horizon]
    dates = np.sort(df["date"].unique())
    cutoff = pd.Timestamp(cutoff)
    last = last_trainable_date(dates, cutoff, h_days)
    if last is None:
        raise ValueError(f"No {horizon} labels are known by {cutoff.date()}")

    start = pd.to_datetime(cfg["splits"]["train_start"])
    rows = df[(df["date"] >= start) & (df["date"] <= last) & df[target].notna()]
    feats = feature_columns(df)

    pre = make_preprocessor(cfg)
    with _quiet_preprocessor():
        X = pre.fit_transform(rows[feats])
    y_int = (rows[target].astype(int) == 1).astype(int)
    est = fit_estimator(name, cfg, X, y_int)

    model = DirectionModel(est, pre.get_feature_names(), horizon,
                           f"{name}_{horizon}", threshold=threshold)
    info = {
        "cutoff": cutoff.date().isoformat(),
        "labels_through": last.date().isoformat(),
        "rows": int(len(rows)),
        "n_eff": effective_n(rows, h_days),
    }
    return model, pre, info


def walk_forward(df: pd.DataFrame, horizon: str, name: str, threshold: float,
                 cfg: dict, start, end=None, log_every: int = 50) -> pd.DataFrame:
    """
    One model per day. For every session d from `start`:

      1. fit a fresh preprocessor and model on the rows whose label had been
         decided by the close of d -- as-of dates at least h sessions before d;
      2. score ONLY day d (one row per symbol) with that model, then discard it.

    No day is scored by a model that saw its own outcome, any later date, or
    even a later day's features: the imputer medians, the dropped-feature list
    and the model weights are all re-derived from history alone, every day.
    This is also exactly what the daily job does live, so a history rebuilt
    from this is the same process the site serves, not a reconstruction.

    Returns one row per (symbol, day): the raw p_up, the call, the date the
    model's training labels ran through, how many rows it was fit on, and the
    true label where it is already known.
    """
    import time

    target = f"y_class_{horizon}"
    h_days = HORIZON_DAYS[horizon]
    dates = np.sort(df["date"].unique())
    days = dates[dates >= np.datetime64(pd.Timestamp(start))]
    if end is not None:
        days = days[days <= np.datetime64(pd.Timestamp(end))]

    out = []
    t0 = time.time()
    for i, d in enumerate(days):
        d = pd.Timestamp(d)
        model, pre, info = fit_through(df, horizon, name, threshold, cfg, d)

        # The guarantee, checked rather than assumed: the newest training row's
        # label resolves on d at the latest, and nothing dated d or later was fit.
        labels_through = pd.Timestamp(info["labels_through"])
        assert labels_through < d, f"{horizon} model for {d.date()} trained on {labels_through.date()}"

        rows = df[df["date"] == d]
        with _quiet_preprocessor():
            X = pre.transform(rows[pre.get_feature_names()])
        p_up = model.predict_proba(X)[:, 1]
        out.append(pd.DataFrame({
            "symbol": rows["symbol"].values,
            "as_of_date": d,
            "labels_through": labels_through,
            "train_rows": info["rows"],
            "p_up_raw": p_up,
            "threshold": float(threshold),
            "pred_class": np.where(p_up >= threshold, 1, -1),
            "y_true": rows[target].values,
        }))
        if log_every and (i + 1) % log_every == 0:
            rate = (time.time() - t0) / (i + 1)
            logger.info("    %s day %d/%d (%s)  ~%.0fs left", horizon, i + 1, len(days),
                        d.date(), rate * (len(days) - i - 1))

    if not out:
        return pd.DataFrame()
    wf = pd.concat(out, ignore_index=True)
    wf["correct"] = np.where(wf["y_true"].notna(), wf["pred_class"] == wf["y_true"], np.nan)
    return wf


def walk_forward_metrics(wf: pd.DataFrame, horizon: str) -> Optional[Dict]:
    """Score each day's call against that day's own outcome, then summarise."""
    lab = wf[wf["y_true"].notna()]
    if lab.empty:
        return None
    y = lab["y_true"].astype(int)
    y_bin = (y == 1).astype(int)
    per_day = lab.groupby("as_of_date")["correct"].mean()
    return {
        "n": int(len(lab)),
        "days": int(lab["as_of_date"].nunique()),
        "n_eff": effective_n(lab.rename(columns={"as_of_date": "date"}), HORIZON_DAYS[horizon]),
        "accuracy": float(accuracy_score(y, lab["pred_class"])),
        "balanced_accuracy": float(balanced_accuracy_score(y, lab["pred_class"])),
        "roc_auc": float(roc_auc_score(y_bin, lab["p_up_raw"])) if y_bin.nunique() > 1 else float("nan"),
        "up_rate_pred": float((lab["pred_class"] == 1).mean()),
        "eval_up_rate": float(y_bin.mean()),
        "share_days_all_correct": float((per_day == 1).mean()),
        "share_days_all_wrong": float((per_day == 0).mean()),
    }


def save_walk_forward(wf: pd.DataFrame, horizon: str, name: str) -> str:
    """Every day's call, with the date its model's training data ended. Auditable."""
    out = os.path.join(ARTIFACTS, "reports", horizon)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "walk_forward.csv")
    w = wf.copy()
    w.insert(2, "model_name", name)
    for c in ("as_of_date", "labels_through"):
        w[c] = pd.to_datetime(w[c]).dt.date.astype(str)
    w.to_csv(path, index=False, float_format="%.6f")
    return path


def train_horizon(horizon: str, cfg: dict, df: pd.DataFrame) -> Dict:
    target = f"y_class_{horizon}"
    logger.info("=" * 72)
    logger.info("HORIZON %s  (target %s)", horizon.upper(), target)
    logger.info("=" * 72)

    data = df[df[target].notna()].copy()
    data[target] = data[target].astype(int)
    logger.info("Labelled rows: %d (%s to %s)",
                len(data), data["date"].min().date(), data["date"].max().date())

    h_days = HORIZON_DAYS[horizon]
    sp = horizon_splits(cfg, h_days, data)
    logger.info("Validation window sized for this horizon: %d sessions "
                "(~%d non-overlapping %s windows), %s to %s",
                sp["val_sessions"], sp["val_sessions"] // h_days, horizon,
                sp["val_start"].date(), sp["val_end"].date())

    tr = data[(data["date"] >= sp["train_start"]) & (data["date"] <= sp["train_end"])]
    va = data[(data["date"] >= sp["val_start"]) & (data["date"] <= sp["val_end"])]
    te = data[(data["date"] >= sp["test_start"]) & (data["date"] <= sp["test_end"])]

    # Purge each split's tail: those labels resolve inside the NEXT split.
    # Scales with the horizon, so the 20d model gives up 20 sessions per symbol
    # per boundary and the 1d model only one.
    n_before = len(tr) + len(va)
    tr = purge_boundary(tr, h_days)
    va = purge_boundary(va, h_days)
    logger.info("Purged %d boundary rows whose %s labels resolved in the next split",
                n_before - len(tr) - len(va), horizon)

    n_eff = {nm: effective_n(part, h_days)
             for nm, part in (("train", tr), ("val", va), ("test", te))}

    for nm, part in (("train", tr), ("val", va), ("test", te)):
        if part.empty:
            raise ValueError(f"{nm} split is empty for horizon {horizon}")
        up = (part[target] == 1).mean()
        logger.info("  %-5s %5d rows (n_eff %4d)  %s..%s  up-rate %.3f",
                    nm, len(part), n_eff[nm],
                    part["date"].min().date(), part["date"].max().date(), up)

    feats = feature_columns(data)
    logger.info("Feature count before preprocessing: %d", len(feats))

    pre = make_preprocessor(cfg)
    X_tr = pre.fit_transform(tr[feats])
    X_va = pre.transform(va[feats], split_name="val")
    X_te = pre.transform(te[feats], split_name="test")
    kept = pre.get_feature_names()

    y_tr, y_va, y_te = tr[target], va[target], te[target]
    y_tr_int = (y_tr == 1).astype(int)

    results = {}
    for name, mcfg in cfg["models"].items():
        if not mcfg.get("enabled", True):
            continue
        logger.info("-" * 72)
        logger.info("Training %s (%s)", name, horizon)

        est = fit_estimator(name, cfg, X_tr, y_tr_int)
        model = DirectionModel(est, kept, horizon, f"{name}_{horizon}")
        model.threshold = tune_threshold(model, X_va, y_va, n_eff["val"])
        m = {
            "train": evaluate(model, X_tr, y_tr, "train", y_tr),
            "val": evaluate(model, X_va, y_va, "val", y_tr),
            "test": evaluate(model, X_te, y_te, "test", y_tr),
        }
        logger.info("  val  acc %.4f (majority %.4f, edge %+.4f)  auc %.4f",
                    m["val"]["accuracy"], m["val"]["majority_class"],
                    m["val"]["edge_vs_majority"], m["val"]["roc_auc"])
        logger.info("  test acc %.4f (majority %.4f, edge %+.4f)  auc %.4f  bal-acc %.4f",
                    m["test"]["accuracy"], m["test"]["majority_class"],
                    m["test"]["edge_vs_majority"], m["test"]["roc_auc"],
                    m["test"]["balanced_accuracy"])
        up = m["test"]["up_rate_pred"]
        if up > 0.90 or up < 0.10:
            logger.warning("  DEGENERATE: predicts one class %.1f%% of the time. Its "
                           "headline accuracy is the base rate, not skill.", 100 * max(up, 1 - up))

        save_model(model, pre, name, horizon, cfg, m, kept)
        results[name] = m

    metric = cfg["selection"]["metric"]
    best = max(results, key=lambda n: results[n]["val"][metric])
    logger.info("=" * 72)
    logger.info("BEST for %s by val %s: %s (val %.4f, test %.4f)",
                horizon, metric, best,
                results[best]["val"][metric], results[best]["test"][metric])

    threshold = results[best]["val"]["threshold"]

    # Score the selected model the way it is deployed: a fresh fit for every
    # test day, on labels known by that day's close, scoring that day only.
    logger.info("Walk-forward over the test period: one refit per day ...")
    wf_rows = walk_forward(df, horizon, best, threshold, cfg, sp["test_start"])
    wf = walk_forward_metrics(wf_rows, horizon) if not wf_rows.empty else None
    if wf:
        path = save_walk_forward(wf_rows, horizon, best)
        logger.info("  daily refit  bal-acc %.4f  auc %.4f  calls UP %.1f%%  "
                    "(%d days, n_eff %d)  vs frozen bal-acc %.4f  auc %.4f",
                    wf["balanced_accuracy"], wf["roc_auc"], 100 * wf["up_rate_pred"],
                    wf["days"], wf["n_eff"],
                    results[best]["test"]["balanced_accuracy"], results[best]["test"]["roc_auc"])
        logger.info("  per-day calls written to %s", path)
        if wf["up_rate_pred"] > 0.90 or wf["up_rate_pred"] < 0.10:
            logger.warning("  DEGENERATE walk-forward: one class %.1f%% of the time.",
                           100 * max(wf["up_rate_pred"], 1 - wf["up_rate_pred"]))

    write_pointer(horizon, best, results[best], walk_forward=wf)
    return {"horizon": horizon, "best_model": best, "results": results,
            "n_eff": n_eff, "val_window": sp["val_sessions"],
            "train_end": sp["train_end"], "walk_forward": wf}


def save_model(model, preprocessor, name, horizon, cfg, metrics, feature_names):
    out = os.path.join(ARTIFACTS, "models", f"{name}_{horizon}")
    os.makedirs(out, exist_ok=True)
    joblib.dump(model, os.path.join(out, "model.pkl"))
    joblib.dump(preprocessor, os.path.join(out, "preprocessor.pkl"))
    meta = {
        "model_name": f"{name}_{horizon}",
        "algorithm": name,
        "horizon": horizon,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_features": len(feature_names),
        "threshold": float(model.threshold),
        "feature_names": feature_names,
        "config": cfg,
        "metrics": metrics,
    }
    with open(os.path.join(out, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)


def write_pointer(horizon: str, best: str, metrics: Dict,
                  walk_forward: Optional[Dict] = None):
    """
    Record which algorithm and threshold inference uses for this horizon.

    The daily job does not load a pickled model: it refits `model_name` on
    every label known that day (`"refit": "daily"`). `artifact_dir` is the
    frozen candidate the selection was made on, kept for inspection.
    """
    path = os.path.join(ARTIFACTS, "models", "best_models.json")
    current = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            current = json.load(fh)
    current[horizon] = {
        "model_name": best,
        "artifact_dir": f"{best}_{horizon}",
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "val_accuracy": metrics["val"]["accuracy"],
        "val_edge_vs_majority": metrics["val"]["edge_vs_majority"],
        "test_accuracy": metrics["test"]["accuracy"],
        "test_edge_vs_majority": metrics["test"]["edge_vs_majority"],
        "test_roc_auc": metrics["test"]["roc_auc"],
        "threshold": metrics["val"]["threshold"],
    }
    current[horizon]["refit"] = "daily"
    if walk_forward:
        current[horizon]["walk_forward_test"] = walk_forward
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2)
    logger.info("Updated %s", path)


def write_report(all_results: List[Dict]):
    lines = [
        "# Multi-Horizon Direction Model Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Binary UP/DOWN classification.",
        "",
        "**vs baseline** is accuracy minus the always-UP rate. **Bal-acc** is balanced",
        "accuracy, the mean of per-class recall: 0.50 means no discrimination no matter",
        "how high plain accuracy looks. **Calls UP** is the share of predictions that",
        "were UP -- if it approaches 100%, the model has collapsed to the majority class",
        "and its headline accuracy is the base rate rather than skill (flagged ⚠).",
        "",
        "Each horizon is a separate problem: its own base rate (up-rates rise with",
        "horizon), its own purged split boundaries, and its own effective sample size.",
        "Row counts are NOT sample sizes -- consecutive 20-day windows share 19 of their",
        "20 days and SPY/QQQ/DIA/IWM are near-copies, so 25,748 rows carry only a few",
        "hundred independent events. Every error bar is sized on the effective count.",
        "",
        "**Two kinds of test score.** The candidate table scores models *frozen* at the",
        "end of their training window -- that is how the algorithm and threshold are",
        "chosen. The deployed model is not frozen: **every day it is refit from scratch**",
        "on the labels known by that day's close, scores that one day, and is thrown",
        "away. **As deployed** replays exactly that over the test period -- one model",
        "per day, each day scored against its own outcome -- so it is the out-of-sample",
        "record of what the site serves. Every one of those calls, with the date its",
        "training data ended, is in `reports/<h>/walk_forward.csv`.",
        "",
    ]
    for res in all_results:
        h = res["horizon"]
        ne = res.get("n_eff", {})
        lines += [
            f"## {h.upper()} horizon", "",
            f"Independent events (overlapping windows and four correlated ETFs collapsed): "
            f"**train {ne.get('train', '?')}, val {ne.get('val', '?')}, test {ne.get('test', '?')}**. "
            f"Validation spans {res.get('val_window', '?')} sessions to hold a comparable "
            f"number of events at this horizon.", "",
                  "| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |",
                  "|---|---|---|---|---|---|---|"]
        for name, m in res["results"].items():
            star = " **(selected)**" if name == res["best_model"] else ""
            t = m["test"]
            flag = " ⚠" if t["up_rate_pred"] > 0.90 or t["up_rate_pred"] < 0.10 else ""
            lines.append(
                f"| {name}{star} | {m['val']['threshold']:.3f} | {t['accuracy']:.4f} "
                f"| {t['edge_vs_majority']:+.4f} | {t['balanced_accuracy']:.4f} "
                f"| {100 * t['up_rate_pred']:.1f}%{flag} | {t['roc_auc']:.4f} |")
        b = res["results"][res["best_model"]]["test"]
        lines += ["",
                  f"Test baseline (majority class): {b['majority_class']:.4f} on {b['n']} rows; "
                  f"actual up-rate {b['eval_up_rate']:.4f}.",
                  ""]

        wf = res.get("walk_forward")
        if wf:
            frozen_to = pd.Timestamp(res["train_end"]).date()
            flag = " ⚠" if wf["up_rate_pred"] > 0.90 or wf["up_rate_pred"] < 0.10 else ""
            lines += [f"**As deployed** ({res['best_model']}, test period):", "",
                      "| Fit | Test bal-acc | Test AUC | Calls UP | Independent events |",
                      "|---|---|---|---|---|",
                      f"| Frozen, trained through {frozen_to} | {b['balanced_accuracy']:.4f} "
                      f"| {b['roc_auc']:.4f} | {100 * b['up_rate_pred']:.1f}% "
                      f"| {ne.get('test', '?')} |",
                      f"| Refit daily ({wf['days']} separate models) | {wf['balanced_accuracy']:.4f} "
                      f"| {wf['roc_auc']:.4f} | {100 * wf['up_rate_pred']:.1f}%{flag} "
                      f"| {wf['n_eff']} |",
                      "",
                      f"Up-rate over these days: {wf['eval_up_rate']:.3f}. Days where all four "
                      f"ETF calls were right: {100 * wf['share_days_all_correct']:.1f}%; all four "
                      f"wrong: {100 * wf['share_days_all_wrong']:.1f}% -- the four move together, "
                      f"so a day is closer to one event than four.",
                      ""]
    path = os.path.join(ARTIFACTS, "reports", "model_report.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    logger.info("Wrote %s", path)


def main():
    ap = argparse.ArgumentParser(description="Train direction models")
    ap.add_argument("--horizon", choices=HORIZONS)
    ap.add_argument("--all", action="store_true", help="Train every horizon")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--no-cache", action="store_true", help="Re-pull the dataset from Supabase")
    args = ap.parse_args()

    if not args.horizon and not args.all:
        ap.error("pass --horizon {1d,5d,20d} or --all")

    os.makedirs(ARTIFACTS, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(os.path.join(ARTIFACTS, "training.log"),
                                      mode="w", encoding="utf-8")],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    cfg = load_config(args.config)
    df = build_dataset(use_cache=not args.no_cache)
    df, _ = to_stationary_features(df)

    horizons = HORIZONS if args.all else (args.horizon,)
    results = [train_horizon(h, cfg, df) for h in horizons]
    write_report(results)

    logger.info("=" * 72)
    logger.info("TRAINING COMPLETE")
    for r in results:
        b = r["results"][r["best_model"]]["test"]
        wf = r.get("walk_forward") or {}
        logger.info("  %-4s best=%-22s frozen bal-acc %.4f auc %.4f | refit daily "
                    "bal-acc %.4f auc %.4f calls UP %.1f%%",
                    r["horizon"], r["best_model"], b["balanced_accuracy"], b["roc_auc"],
                    wf.get("balanced_accuracy", float("nan")), wf.get("roc_auc", float("nan")),
                    100 * wf.get("up_rate_pred", float("nan")))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
