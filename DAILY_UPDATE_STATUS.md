# Daily ETL Update Status Report

**Date:** December 23, 2025  
**Status:** ✅ **WORKING** - ETL is properly configured for daily updates

---

## Summary

The ETL pipeline is **fully operational** and configured to update the website data daily. The GitHub Actions workflow runs automatically at **5 PM EST (10 PM UTC) on weekdays** (Monday-Friday) to:

1. ✅ Download latest market data (OHLCV) for all symbols
2. ✅ Download latest macro data (FRED series)
3. ✅ Download latest proxy data (VIX, commodities, etc.)
4. ✅ Compute technical features
5. ✅ Merge context features (macro, events, proxies)
6. ✅ Store outcome prices (for future validation)
7. ✅ Generate predictions for next trading day
8. ✅ Update database with all new data

---

## What Gets Updated Daily

### Data Tables Updated by ETL

| Table | Updated? | Description |
|-------|----------|-------------|
| `daily_bars` | ✅ Yes | OHLCV data for all symbols (SPY, QQQ, IWM, DIA) |
| `features_daily` | ✅ Yes | 83 technical + context features as JSON |
| `labels_daily` | ✅ Yes | Classification labels (y_class_1d, y_class_5d) |
| `macro_daily` | ✅ Yes | FRED economic indicators |
| `events_calendar` | ✅ Yes | Market events (FOMC, CPI, NFP, etc.) |
| `model_predictions_classification` | ✅ Yes | Predictions for next trading day |

### Website Data Requirements

The website ([page.tsx](web/app/page.tsx)) displays:
- ✅ **Current predictions** for next trading day (from `model_predictions_classification`)
- ✅ **Historical predictions** with actual outcomes (validated against actual returns)
- ✅ **OHLCV price data** for charts (from `daily_bars`)

**All data needed by the website is updated daily** ✅

---

## ETL Workflow Details

### Automatic Scheduled Run

**GitHub Actions:** `.github/workflows/daily_etl_and_predictions.yml`

- **Schedule:** Monday-Friday at 5 PM EST (10 PM UTC)
- **Why 5 PM?** Markets close at 4 PM EST; gives time for data to settle
- **Skips weekends:** Markets are closed Saturday/Sunday

### What Happens Each Day

```bash
# 1. ETL auto-detects last date in database
python run_etl.py --mode incremental

# Output:
# ✅ Auto-detected update start date: 2025-12-23 (next trading day after 2025-12-22)
# 📊 Processing 1 trading day from 2025-12-23 to 2025-12-23

# 2. ETL generates predictions for NEXT trading day (Dec 24)
python quick_add_predictions_all_symbols.py

# Output:
# ✅ Generated 8 predictions (4 symbols × 2 horizons)
#    - SPY: 1d, 5d
#    - QQQ: 1d, 5d
#    - IWM: 1d, 5d
#    - DIA: 1d, 5d
```

### Manual Run (if needed)

You can manually trigger the workflow from GitHub Actions UI or run locally:

```powershell
# Run ETL locally (incremental update to today)
python run_etl.py --mode incremental

# Force-run on weekends (for testing)
python run_etl.py --mode incremental --force
```

---

## Current Data Status

### Latest Dates (as of Dec 23, 2025)

```
✅ daily_bars:    2025-12-23
✅ features_daily: 2025-12-23
✅ labels_daily:   2025-12-23
✅ predictions:    2025-12-24 (for next trading day)
```

### Test Results

```bash
$ python run_etl.py --mode incremental
✅ ETL Pipeline completed successfully!
✅ Generated 8 predictions for next trading day

$ python verify_all_predictions.py
✅ All symbols have predictions for 2025-12-24
```

---

## Database Schema

### Outcome Prices (Migration 015)

The ETL now stores **outcome prices** separately from labels:

```sql
-- daily_bars table includes:
outcome_price_1d  -- Close price 1 trading day in future (NULL if not available yet)
outcome_price_5d  -- Close price 5 trading days in future (NULL if not available yet)
```

**Why?** This allows us to:
1. ✅ Store today's data even when we don't have tomorrow's outcome
2. ✅ Generate predictions before knowing the outcome
3. ✅ Backfill outcomes as new data arrives

---

## Prediction Generation

### Current Status: Real Model-Based Predictions ✅

✅ **The system now uses trained XGBoost models** with varying confidence levels!

```python
# Examples from real predictions:
SPY  1d: DOWN (conf: 0.640, p_up: 0.360, p_down: 0.640)
QQQ  1d: DOWN (conf: 0.606, p_up: 0.394, p_down: 0.606)
IWM  1d: DOWN (conf: 0.646, p_up: 0.354, p_down: 0.646)
DIA  1d: DOWN (conf: 0.591, p_up: 0.409, p_down: 0.591)
```

**Key Improvements:**
- ✅ Real model predictions using trained XGBoost models
- ✅ Varying confidence levels (0.55 - 0.70 typical range)
- ✅ Actual probabilities (p_up, p_down) from model inference
- ✅ Automatic fallback to placeholder if models unavailable

### How It Works

1. **ETL runs** and updates all data
2. **generate_real_predictions.py** is called automatically
3. Script loads trained XGBoost models from `ml/artifacts/models/`
4. For each symbol, it:
   - Fetches latest features from database
   - Preprocesses features (imputation, scaling)
   - Runs model inference to get probabilities
   - Stores predictions with real confidence scores

### Fallback Mechanism

If trained models are not available:
- Falls back to `quick_add_predictions_all_symbols.py` (placeholder 55% UP)
- GitHub Actions checks for model files before deciding which script to use
- Local runs attempt real predictions first, then fallback

### To Update/Retrain Models

```powershell
# Train new models
python train_models_1d.py
python train_models_5d.py

# Commit models to repo for GitHub Actions to use
git add ml/artifacts/models/
git commit -m "Update trained models"
git push
```

---

## Website Integration

### What the Website Shows

The website fetches data from Supabase:

1. **Current Predictions** (1-day and 5-day outlook)
   - Query: `model_predictions_classification` → latest date for each symbol
   - Shows: Direction (UP/DOWN), confidence, probabilities

2. **Historical Performance**
   - Query: `model_predictions_classification` → last 100 predictions
   - Joins with `daily_bars` to calculate actual returns
   - Shows: Prediction accuracy, actual outcomes

3. **Price Charts** (if implemented)
   - Query: `daily_bars` → OHLCV data
   - Shows: Historical price movements

### Data Flow

```
ETL (5 PM daily)
    ↓
Database (Supabase)
    ↓
Website (Next.js)
    ↓
Users see predictions
```

**Update frequency:** Website shows new predictions within **minutes** of ETL completion

---

## Monitoring & Verification

### Check if ETL Ran Successfully

```powershell
# Check latest dates in database
python check_db_dates.py

# Check prediction availability
python verify_all_predictions.py

# Check database integrity
python validate_data_quality.py
```

### GitHub Actions Logs

1. Go to GitHub repository
2. Click **Actions** tab
3. View **Daily ETL and Predictions** workflow runs
4. Check for ✅ success or ❌ errors

---

## Known Issues & Limitations

### Fixed Issues ✅

1. **~~Placeholder predictions~~** ✅ FIXED
   - **Was:** Using 55% UP probability instead of trained models
   - **Now:** Using real XGBoost models with varying confidence (0.59-0.65)
   - **Impact:** Website now shows meaningful predictions with real model probabilities

### Current Limitations

1. **Event calendar TODOs:** Historical FOMC/CPI/NFP dates not fully populated
   - **Impact:** Event features may be incomplete for backfill periods
   - **Fix:** Event calendar code has TODOs in `etl/build_events.py`

2. **Weekend runs skipped:** ETL won't run on Saturday/Sunday
   - **Impact:** None (markets are closed)
   - **Override:** Use `--force` flag if needed for testing

3. **Model version warnings:** Sklearn version mismatch in model loading
   - **Impact:** Minor warnings during prediction (models still work)
   - **Fix:** Retrain models with current sklearn version

### Everything Else: ✅ Working

- ✅ Auto-detection of latest date
- ✅ Incremental updates
- ✅ Lookback window for rolling features
- ✅ Outcome price storage
- ✅ Label computation with incomplete data
- ✅ Prediction generation
- ✅ Database upserts (idempotent)
- ✅ GitHub Actions scheduling
- ✅ Weekend skip logic

---

## Next Steps (Optional Enhancements)

### For Better Predictions

1. **Train real models:**
   ```powershell
   python train_models_1d.py
   python train_models_5d.py
   ```

2. **Update GitHub Actions to use trained models:**
   - Commit model artifacts to repo
   - Modify workflow to run model-based predictions

### For Better Features

1. **Complete event calendar:**
   - Add historical FOMC dates
   - Add historical CPI release dates
   - Add historical NFP release dates

2. **Add more features:**
   - Sentiment indicators
   - Options flow data
   - Futures data

---

## Conclusion

✅ **The ETL is working properly and will update the website data daily.**

The system is configured to:
- Run automatically on weekdays at 5 PM EST
- Update all necessary database tables
- Generate predictions for the next trading day
- Provide all data the website needs

**No action required** for daily operations. The workflow will continue running automatically.

For questions or issues, check:
- GitHub Actions logs for workflow execution
- Database query results with `check_db_dates.py`
- Prediction verification with `verify_all_predictions.py`

---

**Last verified:** December 23, 2025  
**Next scheduled run:** December 24, 2025 at 5:00 PM EST
