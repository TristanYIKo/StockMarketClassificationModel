# GitHub Actions Workflow Diagram

## Daily Automated Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Actions Trigger                        │
│                                                                  │
│  ⏰ Scheduled: Every day at 5 PM EST                            │
│  👆 Manual: Via Actions tab with optional date parameters        │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Setup Environment                            │
│                                                                  │
│  ✓ Checkout code                                                │
│  ✓ Install Python 3.11                                          │
│  ✓ Install dependencies (pip)                                   │
│  ✓ Load secrets (SUPABASE_URL, SUPABASE_KEY, FRED_API_KEY)     │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ETL Pipeline (etl/main.py)                    │
│                                                                  │
│  📊 Extract:                                                     │
│     • Yahoo Finance → OHLCV data for SPY, QQQ, IWM              │
│     • FRED API → Macro indicators (VIX, DGS10, etc.)            │
│     • Proxy data → Sector ETFs, commodities                     │
│                                                                  │
│  🔄 Transform:                                                   │
│     • Technical indicators (RSI, MACD, Bollinger, etc.)         │
│     • Lag features (1d, 5d, 20d lags)                           │
│     • Regime classifications (trend, volatility)                │
│     • Context features (macro, relative strength)               │
│                                                                  │
│  💾 Load:                                                        │
│     • Upsert to Supabase tables                                 │
│     • daily_bars, features_json, labels, events                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│          Generate Predictions (ml/src/predict/*.py)              │
│                                                                  │
│  🤖 Load Models:                                                 │
│     • XGBoost classifiers for 1d and 5d horizons                │
│     • Preprocessors and calibrators                             │
│     • Threshold configurations                                  │
│                                                                  │
│  🔮 Predict:                                                     │
│     • Fetch latest features from Supabase                       │
│     • Generate probability predictions                          │
│     • Apply calibration                                         │
│     • Apply gating (confidence + margin thresholds)             │
│                                                                  │
│  💾 Store:                                                       │
│     • Upsert predictions to model_predictions_classification    │
│     • Include probabilities, final predictions, confidence      │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Verify and Report                             │
│                                                                  │
│  ✓ Run validation checks (check_db_dates.py)                    │
│  ✓ Display summary with timestamp                               │
│  ✓ Send notifications if failures                               │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Result: Updated Database                      │
│                                                                  │
│  ✅ Latest market data through current date                     │
│  ✅ Fresh predictions for next trading day(s)                   │
│  ✅ Ready for web dashboard or trading decisions                │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
External APIs          ETL Pipeline         Database          Predictions
─────────────         ──────────────      ──────────         ────────────

┌──────────┐                              ┌─────────┐
│  Yahoo   │──┐                           │ Supabase│
│ Finance  │  │                           │         │
└──────────┘  │    ┌──────────┐          │ Tables: │       ┌─────────┐
              ├───→│          │          │         │       │ Models  │
┌──────────┐  │    │   ETL    │─────────→│ • bars  │──────→│ (XGB)   │
│   FRED   │──┤    │  (main)  │          │ • feats │       │         │
└──────────┘  │    │          │          │ • labels│       └────┬────┘
              │    └──────────┘          │ • events│            │
┌──────────┐  │                          └─────────┘            │
│ Proxies  │──┘                                                 │
│ (Sector) │                                                    ▼
└──────────┘                              ┌─────────────────────────┐
                                          │   Predictions Table     │
                                          │ • symbol, date, horizon │
                                          │ • p_down, p_up          │
                                          │ • pred_class_final      │
                                          │ • confidence, margin    │
                                          └─────────────────────────┘
```

## File Structure

```
.github/
├── workflows/
│   └── daily_etl_and_predictions.yml    ← Main workflow file
├── GITHUB_ACTIONS_SETUP.md              ← Detailed setup guide
├── QUICK_START_ACTIONS.md               ← Quick reference
├── DEBUGGING_GUIDE.md                   ← Troubleshooting help
├── STATUS_BADGES.md                     ← Badge setup
└── WORKFLOW_DIAGRAM.md                  ← This file

etl/
├── main.py                              ← ETL entry point
├── extract_*.py                         ← Data extraction
├── transform_*.py                       ← Feature engineering
└── load_db.py                           ← Database upsert

ml/
└── src/
    └── predict/
        └── predict_and_store.py         ← Prediction pipeline
```

## Timing Example

**Scenario**: Workflow runs Monday at 5:00 PM EST

```
Timeline:
─────────
5:00 PM EST  → GitHub Actions triggers workflow
5:01 PM      → Environment setup (1 min)
5:02 PM      → ETL starts
5:08 PM      → ETL completes (6 min)
5:09 PM      → Predictions start
5:12 PM      → Predictions complete (3 min)
5:13 PM      → Verification runs
5:14 PM      → ✅ Workflow complete (14 min total)

Result:
───────
✓ Database updated with Monday's market data
✓ Predictions generated for Tuesday
✓ Dashboard shows fresh data
```

## Error Handling Flow

```
┌──────────┐
│  Step 1  │
└────┬─────┘
     │ Success
     ▼
┌──────────┐
│  Step 2  │
└────┬─────┘
     │ Success
     ▼
┌──────────┐
│  Step 3  │ ──── Error! ───→ ┌──────────────────┐
└──────────┘                  │ • Workflow fails  │
                              │ • Email sent      │
                              │ • Status: ❌      │
                              │ • Logs available  │
                              └──────────────────┘

Steps continue on success,
stop on first failure
```

## Manual vs Scheduled Runs

### Scheduled Run (Default)
```
Trigger: Cron schedule (daily at 5 PM)
Dates:   Automatic (latest DB date → today)
Mode:    Incremental
```

### Manual Run (Custom)
```
Trigger: User clicks "Run workflow"
Dates:   User-specified (optional)
Mode:    Incremental
Options: --start, --end parameters
```

## Resource Usage

```
GitHub Actions Free Tier: 2,000 minutes/month
Average workflow runtime:  5-15 minutes
Runs per month:           ~30 (daily)
Total usage:              150-450 minutes/month
Remaining:                1,550-1,850 minutes ✓
```

## Success Criteria

✅ **Workflow succeeds if**:
- All dependencies install correctly
- API keys are valid and have quota remaining
- Data is available (trading day)
- Models exist and can load
- Database connection successful
- Predictions generate without errors

❌ **Workflow fails if**:
- Missing or invalid secrets
- API rate limits exceeded
- Network connectivity issues
- Model files missing
- Database authentication fails
- Python errors in ETL or prediction code
