# Market Direction Model

Multi-horizon **binary direction classifiers** for four US index ETFs — SPY, QQQ,
DIA, IWM — served through a Next.js dashboard.

Each model answers one question: *will the close `h` trading days from now be
higher than today's close?* Three horizons are trained and served: **1D, 5D, 20D**.

---

## Architecture

```
yfinance ─┐
FRED ─────┼──▶ etl/  ──▶ Supabase ──▶ ml/src/data ──▶ ml/src/train ──▶ artifacts
NYSE cal ─┘   (features,  (daily_bars,   (dataset       (per-horizon    (models +
               labels)    features_daily, builder)       models)         report)
                          labels_daily)                      │
                                                             ▼
                                        Supabase.predictions ◀── ml/src/predict
                                                             │
                                                             ▼
                                                        web/ (Next.js)
```

### Daily loop (GitHub Actions, `.github/workflows/daily_pipeline.yml`)

1. `run_etl.py --mode incremental` — auto-detects the last loaded session and
   pulls forward to today: OHLCV, macro series, cross-asset proxies, events,
   engineered features, and labels.
2. `python -m ml.src.predict.predict --latest` — one prediction per symbol ×
   horizon from the newest feature row.
3. `python -m ml.src.predict.predict --resolve` — fills in outcomes for calls
   whose target session has since closed.

### Monthly loop (`.github/workflows/monthly_retrain.yml`)

Retrains all three horizons, rebuilds stored predictions, and commits the
refreshed artifacts. The commit doubles as repo activity, which is what stops
GitHub from disabling the daily schedule after 60 idle days.

---

## Setup

```bash
pip install -r requirements.txt -r ml/requirements.txt
```

`.env` in the repo root (pipeline — needs write access):

```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>   # preferred; bypasses RLS
SUPABASE_KEY=<anon key>                   # fallback only
FRED_API_KEY=<key>
```

`web/.env.local` (site — read-only, **server-side only**):

```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<anon key>
```

Note the absence of a `NEXT_PUBLIC_` prefix. Next.js inlines any `NEXT_PUBLIC_*`
value referenced from client-bundled code, so the prefix is itself the hazard.
All Supabase access happens in server components; `web/lib/supabase.ts` imports
`server-only`, which turns an accidental client import into a build error rather
than a silent credential leak.

The same variables must be set in the hosting provider's environment settings
(Vercel: Project → Settings → Environment Variables). Remove the old
`NEXT_PUBLIC_*` entries there.

Apply migrations in order through the Supabase SQL editor. DDL cannot be run
with the anon key, so migrations are always a manual step.

---

## Commands

| Task | Command |
|---|---|
| Incremental data load | `python run_etl.py` |
| Full backfill | `python run_etl.py --mode backfill --start 2001-01-01` |
| Train one horizon | `python -m ml.src.train.train --horizon 20d` |
| Train all horizons | `python -m ml.src.train.train --all` |
| Today's predictions | `python -m ml.src.predict.predict --latest` |
| Rebuild history | `python -m ml.src.predict.predict --backfill 2025-01-01` |
| Resolve outcomes | `python -m ml.src.predict.predict --resolve` |
| Run the site | `npm --prefix web run dev` |

---

## How the modelling works

**Target.** `y_class_<h>d ∈ {1, -1}`, from `log(close[t+h] / close[t])`. Labels are
recomputed from the close series at dataset-build time rather than read back from
`labels_daily`, so a new horizon needs no migration and labels can never go stale
relative to prices.

**Splits.** Strictly chronological — train 2001–2023, validate 2024, test 2025
onward. No random sampling, and the test window is never touched during
selection or tuning.

**Stationarity.** Raw price levels (`sma_200`, `close`, proxy closes) are replaced
with scale-free equivalents such as `px_vs_sma_200`. SPY traded near 130 in 2001
and near 770 in 2026, so every test-period level sits outside the range the trees
were fit on; a split on an absolute price sends the whole test set down one branch.
See `ml/src/data/features.py`.

**Decision threshold.** Tuned on validation, not fixed at 0.5. `class_weight=
"balanced"` deliberately shifts the boundary to weight the rarer DOWN class,
which helps ranking but produces an implausibly bearish argmax on a series that
rises in ~68% of 20-day windows. Ranking and thresholding are separate decisions.

**Displayed probabilities.** Stored `p_up` / `p_down` are re-centred so 0.5 is the
decision boundary (`DirectionModel.predict_proba_display`). The raw probabilities
are boundary-shifted by `class_weight="balanced"` — a 20D call can be UP at a raw
`p_up` of 0.27 because the tuned threshold is 0.22 — and showing that verbatim
would put an "UP" badge next to a bar reading "Down 73%". The map is monotone, so
ROC AUC is unchanged; it sends the threshold to 0.5, so argmax agrees with the
call. It is a presentation transform, not a second model.

**Selection.** By validation ROC AUC, not accuracy. Accuracy on this task is
dominated by the base rate, so selecting on it just picks whichever model is most
bullish. AUC measures whether predicted probabilities *rank* up-days above
down-days, which is what the dashboard renders as a confidence bar.

### Each horizon is its own problem

The three horizons are not the same task at three settings. They differ in base
rate, in how much data they actually contain, and in where their labels reach.
All three are handled per horizon:

**Base rate rises with horizon.** Up-rates are 0.54 (1D), 0.57 (5D), 0.62 (20D)
over the full sample — drift compounds. Every threshold is chosen against *that
horizon's own* base rate, and every accuracy figure is quoted beside it. A 20D
model must clear a much higher bar than a 1D model to mean the same thing.

**Row counts are not sample sizes.** Consecutive 20-day windows share 19 of their
20 days, and SPY/QQQ/DIA/IWM are near-copies of each other. So:

| Horizon | Rows | Independent events | Overstated by |
|---|---|---|---|
| 1D | 25,824 | ~6,456 | 4× |
| 5D | 25,808 | ~1,290 | 20× |
| 20D | 25,748 | **~321** | **80×** |

`effective_n()` computes this as distinct dates ÷ horizon, and every error bar —
including the one-standard-error band in threshold tuning — is sized on it.
Previously the band used the row count, so at 20D it was ~9× too tight and the
threshold overfit noise.

**Labels reach across split boundaries.** A 20D label stamped 2023-12-15 is
decided by the close on ~2024-01-16, inside the validation window. `purge_boundary()`
drops the last `h` observations per symbol from each split: 4 rows at 1D, 20 at
5D, 80 at 20D.

**Validation is sized in events, not days.** One calendar year holds ~250
independent 1D events but only ~12 non-overlapping 20D windows. Selecting among
four models on twelve events is noise. The validation window therefore grows with
the horizon (`horizon_splits()`), holding ~40 non-overlapping windows at each —
800 sessions at 20D versus 252 at 1D.

### Honest performance

Out-of-sample (2025-01 onward), selected model per horizon:

| Horizon | Balanced acc | Test AUC | Calls UP | Base rate | Independent test events |
|---|---|---|---|---|---|
| 1D | **0.532** | 0.529 | 53% | 55% | 419 |
| 5D | 0.498 | 0.522 | 38% | 58% | 83 |
| 20D | 0.451 | 0.469 | 40% | 68% | **20** |

**Only the 1D model shows any consistent discrimination**, and it is marginal
(0.532 balanced accuracy, validation 0.530 and test 0.529 agreeing). 5D is at
chance. 20D is below chance on 20 independent test events, which is too few to
conclude anything either way.

An earlier version of this README reported 20D balanced accuracy of 0.551 and
called it "modest but real skill". That was wrong. It came from the leaked split
boundary plus a threshold tuned on eleven effective validation events. Purging the
boundary and sizing the window in events removed it. The dashboard now refuses to
render a verdict for any horizon with fewer than 30 independent events, which is
why 20D reads "too few events" rather than a hit rate.

This is not a trading edge.

#### The failure this replaced

An earlier version tuned the decision threshold to maximise plain accuracy. On an
imbalanced binary target that objective is optimised by collapsing onto the
majority class, and it did: the 1D model called UP on **99.4%** of days. Its
reported accuracy matched the always-UP baseline because it *was* the always-UP
baseline, and nothing in the report revealed it, because the report showed only
accuracy.

Guards now in place:

- `tune_threshold` maximises balanced accuracy under a one-standard-error rule
  sized on effective sample, breaking ties toward the horizon's own base rate.
  When no threshold separates the classes at all, it says so and matches the base
  rate rather than settling on a degenerate all-one-class rule.
- Report and dashboard both show **Calls UP**, balanced accuracy, and independent
  event counts; training logs a `DEGENERATE` warning above 90% one-class.

## Feature hygiene

`features_daily.feature_json` must never contain anything derived from the future.
This was violated once and is worth understanding: an incremental ETL run reads
history back out of `daily_bars` with `select("*")`, and after migration 015 added
`outcome_price_1d` / `outcome_price_5d` to that table, those future closes rode
along through `compute_features` and into the stored feature set. A model trained
on that data scores near 100% and is worthless.

Two guards now:

- `SupabaseDB.BAR_COLUMNS` — history reads select OHLCV explicitly, never `*`.
- `etl.transform_features_context.is_forbidden_feature` — a denylist applied both
  when writing features and when building the training set, so historical rows
  written before the fix are filtered on read.

---

## Security model

The browser never receives a Supabase credential. Verified against a production
build: no key, no JWT, and not even the project ref appears in `.next/static` or
in the server-rendered HTML.

Three layers:

1. **Server-only access.** Every query runs in a server component. `web/lib/supabase.ts`
   imports `server-only` and reads unprefixed env vars.
2. **Read-only public role.** Migration 017 enables RLS on every table with a
   `SELECT`-only policy for `anon` and `authenticated`. No write policy exists, so
   inserts, updates and deletes are denied.
3. **Privileged pipeline.** The ETL authenticates with `SUPABASE_SERVICE_KEY`,
   which bypasses RLS. `SupabaseDB` prefers it and warns when falling back.

**If you are applying this to a live project, order matters:**

1. Add `SUPABASE_SERVICE_KEY` (GitHub Actions secret + local `.env`).
2. Apply `migrations/017_lock_down_public_access.sql`.
3. **Rotate the anon key.** The previous site shipped it in a client bundle, so it
   must be treated as compromised. Update `web/.env.local` and the host's env vars.

Doing 2 before 1 does not lose data, but the pipeline's writes start being rejected.

## Known issues

- Rows in `features_daily` written before the leakage fix still carry the extra
  columns. They are filtered on read; a full feature rebuild would clear them.
- `model_predictions_classification` is superseded by `predictions` and can be
  dropped once nothing references it.

Not investment advice.
