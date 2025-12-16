# Binary Classification Migration Guide

## Overview
Converted the stock market prediction model from **3-class classification (BUY/HOLD/SELL)** to **2-class binary classification (UP/DOWN)**.

## Changes Made

### 1. Database Schema
**File:** `migrations/014_convert_to_binary_classification.sql`

- Dropped old `model_predictions_classification` table
- Created new table with binary structure:
  - `p_down` and `p_up` instead of `p_sell`, `p_hold`, `p_buy`
  - `pred_class_raw` and `pred_class_final` now only contain 1 (UP) or -1 (DOWN)
  - `confidence` is max(p_down, p_up)
  - `margin` is abs(p_up - p_down)

**To apply:**
```bash
# Connect to your Supabase database and run:
psql -h your-db-host -U postgres -d postgres -f migrations/014_convert_to_binary_classification.sql
```

### 2. ETL Pipeline - Label Generation
**File:** `etl/transform_labels.py`

- Updated `compute_labels()` function to generate binary labels
- **New logic:**
  - `y_class_1d = 1` if return > 0 (UP)
  - `y_class_1d = -1` if return <= 0 (DOWN)
- Removed triple-barrier thresholds (±0.25)
- Same applied to `y_class_5d` for 5-day predictions

### 3. Model Training
**File:** `ml/src/train/train_models.py`

- Updated `train_xgboost()` function:
  - Label mapping changed from {-1→0, 0→1, 1→2} to {-1→0, 1→1}
  - Class weights now only for 2 classes
- Other models (LogisticRegression, RandomForest, LightGBM) automatically handle binary classification

### 4. Frontend (Web Application)

#### Types
**File:** `web/components/predictions/types.ts`
- Changed `direction: 'BUY' | 'HOLD' | 'SELL'` to `direction: 'UP' | 'DOWN'`
- Changed `p_buy`, `p_hold`, `p_sell` to `p_up`, `p_down`

#### Main Page
**File:** `web/app/page.tsx`
- Updated `getDirection()` to return 'UP' or 'DOWN'
- Updated data processing to use `p_up` and `p_down`

#### Prediction Cards
**File:** `web/components/predictions/PredictionCard.tsx`
- Updated badge colors for UP (green) and DOWN (red)
- Updated accent line to show only UP or DOWN
- Removed HOLD references

#### Probability Bars
**File:** `web/components/predictions/ProbabilityBars.tsx`
- Simplified to show only 2 bars: UP (green) and DOWN (red)
- Removed HOLD bar
- Updated tooltips and labels

#### Past Predictions Table
**File:** `web/components/predictions/PastPredictionsTable.tsx`
- Updated badge colors for UP/DOWN
- Updated outcome checking logic (UP correct if return > 0, DOWN correct if return < 0)

### 5. Prediction Scripts
**File:** `ml/src/predict/predict_and_store.py`
- Updated `get_raw_predictions()` to expect (N, 2) probabilities
- Updated `create_prediction_dataframe()` to store `p_down` and `p_up`

## Migration Steps

### 1. Run Database Migration
```bash
cd migrations
# Run migration 014 on your Supabase database
```

### 2. Re-generate Labels
```bash
cd etl
python main.py --labels  # Regenerate classification labels
```

### 3. Retrain Models
```bash
cd ml
# For 1-day predictions
python train_models_1d.py --models all

# For 5-day predictions  
python train_models_5d.py --models all
```

### 4. Restart Frontend
```bash
cd web
npm run dev
```

## Key Differences: 3-Class vs Binary

| Aspect | 3-Class (OLD) | Binary (NEW) |
|--------|---------------|--------------|
| **Classes** | BUY (1), HOLD (0), SELL (-1) | UP (1), DOWN (-1) |
| **Probabilities** | p_buy, p_hold, p_sell | p_up, p_down |
| **Label Logic** | Vol-scaled returns with ±0.25 threshold | Simple: return > 0 = UP |
| **Trade Frequency** | ~60% (HOLD reduces trades) | 100% (always predicts UP or DOWN) |
| **Philosophy** | Avoid overtrading in choppy markets | Predict every move |

## Benefits of Binary Classification

1. **Simpler**: Easier to understand and explain
2. **Direct**: Predicts actual market direction
3. **100% Trading**: Makes prediction every day
4. **Balanced**: Typically ~50/50 class distribution

## Potential Drawbacks

1. **No "Do Nothing" Option**: Model must trade even in uncertain conditions
2. **More Friction**: Trading every day increases transaction costs
3. **Chop Risk**: May lose money in sideways/ranging markets

## Files Changed

```
migrations/014_convert_to_binary_classification.sql  [NEW]
etl/transform_labels.py
ml/src/train/train_models.py
ml/src/predict/predict_and_store.py
web/components/predictions/types.ts
web/components/predictions/PredictionCard.tsx
web/components/predictions/ProbabilityBars.tsx
web/components/predictions/PastPredictionsTable.tsx
web/app/page.tsx
```

## Testing

After migration:
1. ✅ Check database has new schema (p_up, p_down columns)
2. ✅ Verify labels are binary (-1, 1) with no 0 values
3. ✅ Confirm models train with 2 classes
4. ✅ Test frontend displays UP/DOWN correctly
5. ✅ Verify probability bars show only 2 colors

## Rollback (If Needed)

To rollback to 3-class classification:
1. Restore `migrations/013_model_predictions_classification.sql`
2. Revert `etl/transform_labels.py` using git
3. Revert all frontend files
4. Retrain models with old code

---
**Date:** December 15, 2025
**Migration:** v3.0 - Binary Classification
