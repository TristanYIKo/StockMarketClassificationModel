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
   engineered features, and labels. It first looks back 120 days for bars with
   no close or missing ETF sessions and, if it finds any, re-loads from there.
2. `python -m ml.src.predict.predict --latest` — fits **today's model** per
   horizon on every label known by today's close, scores today, discards it.
3. `python -m ml.src.predict.predict --resolve` — writes outcomes onto stored
   calls whose target session has since closed. Never re-scores a call.

### Monthly loop (`.github/workflows/monthly_retrain.yml`)

Chooses each horizon's algorithm and threshold on the fixed validation window,
replays the daily process over the whole test period (one model per day),
rebuilds stored predictions from that replay, and commits the refreshed
artifacts. The commit doubles as repo activity, which is what stops GitHub from
disabling the daily schedule after 60 idle days.

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
| Rebuild history (walk-forward) | `python -m ml.src.predict.predict --backfill 2025-01-01` |
| Resolve outcomes | `python -m ml.src.predict.predict --resolve` |
| Any of the above without writing | add `--dry-run` |
| Prove no feature uses later dates | `python validate_no_lookahead.py` (`--control` to test the test) |
| Run the site | `npm --prefix web run dev` |

---

## How the modelling works

**Target.** `y_class_<h>d ∈ {1, -1}`, from `log(close[t+h] / close[t])`. Labels are
recomputed from the close series at dataset-build time rather than read back from
`labels_daily`, so a new horizon needs no migration and labels can never go stale
relative to prices.

**Splits.** Strictly chronological — train 2001–2023, validate 2024, test 2025
onward. No random sampling, and the test window is never touched during
selection or tuning. These splits decide *which* model and threshold to use;
they do not limit what the served model learns from (next paragraph).

**One model per day.** The splits are pinned, so a model fit on the train
window never sees anything after 2023 (late 2021 at 20D, whose validation window
is longer). An earlier version served exactly that frozen fit, so the "monthly
retrain" refit the same old window every month and never learned from a recent
market. Now no model is ever served frozen. For every day `d` — today in the
daily job, and every past day when history is rebuilt — `fit_through()`:

1. takes only rows whose label was already decided at the close of `d`, i.e.
   as-of dates at least `h` sessions before `d` (`last_trainable_date`);
2. fits a fresh preprocessor (dropped-feature list, imputer medians) and a
   fresh model on them;
3. scores `d`'s four rows, one per ETF, and is discarded.

`walk_forward()` asserts on every day that the model's newest training label is
strictly before `d`. The per-day calls, each with the date its training data
ended and the number of rows it was fit on, are written to
`ml/artifacts/reports/<h>/walk_forward.csv`, so the property can be audited
from the file rather than taken on trust. The four ETFs of one day share that
day's model; pooling them is not a leak, since every row in the pool is history.

**History is rebuilt the same way.** Scoring the past with one recent model
would be in-sample, since it trained on that past. `--backfill` reuses the
per-day calls from the retrain (or fits any day they do not cover), so the
site's track record is produced by exactly the process that makes live calls.
`--resolve` only writes outcomes onto stored calls and never re-scores them, so
a recorded call cannot be rewritten after the fact.

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

Out-of-sample, 2025-01-02 to 2026-11-16, scored exactly as deployed — one model
per day, each fit only on labels known by that day's close (retrain of
2026-11-17):

| Horizon | Model | Balanced acc | AUC | Calls UP | Base rate | Independent events | ± 1 SE |
|---|---|---|---|---|---|---|---|
| 1D | logistic regression | 0.507 | 0.512 | 43% | 54% | 461 | 0.023 |
| 5D | logistic regression | 0.475 | 0.475 | 57% | 56% | 91 | 0.052 |
| 20D | XGBoost | 0.390 | 0.403 | 62% | 65% | **22** | 0.107 |

**None of the three is distinguishable from chance.** 1D sits 0.3 standard
errors above 0.50, 5D 0.5 below, 20D 1.0 below on only 22 independent events.
The marginal 1D edge reported in September (0.532) did not survive more test
data and the FRED publication-lag fix. These figures also span 2026-09-14 to
2026-11-16, when ~26% of each day's features were blank (see *A bar without a
close is never stored*); the next retrain after the repair re-scores them.

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

### Every feature for day T is computable at T's close

`python validate_no_lookahead.py` proves it rather than asserting it: for 13
cutoff days per symbol it rebuilds the features with the exact ETL transforms
from history truncated at T and compares row T with the full-history build. All
123 columns match for SPY, QQQ, DIA and IWM. `--control` plants a "tomorrow's
close" column and confirms the test flags it — a check that cannot fail is not
evidence.

That test cannot see data stamped with a date *before it was published*, which
is the FRED case: DGS2/DGS10/T10YIE, EFFR, HY OAS and WALCL are dated by
observation but released the next business day (WALCL: Wednesday's level,
Thursday 4:30pm ET). The historical backfill stored them same-day; the live job
never has them in time. `ml/src/data/features.py` lags those columns one session
on read, for training and inference alike. Removing that leak lowered 1D
validation AUC from 0.530 to 0.524 — small, and in the direction a leak predicts.

### A bar without a close is never stored

yfinance occasionally returns the newest session with volume but NaN prices.
Four Mondays in Sep–Oct 2026 were stored that way for 11 of 14 assets. Because
the incremental load only moves forward, they were never re-fetched, and every
rolling feature whose window contained one went blank: about 26% of each day's
features from 2026-09-14 on, versus 1% before, and the adjacent Friday/Monday
calls could not resolve. Now `drop_incomplete_bars` refuses to store such rows,
and each run's `find_repair_start` looks back 120 days for empty closes or
missing ETF sessions and re-loads from the earliest one, rebuilding the features
and labels after it.

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
