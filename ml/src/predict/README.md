# Multi-Horizon Classification Pipeline

Complete pipeline for generating calibrated predictions with confidence gating for both 1-day and 5-day classification models.

## Pipeline Overview

1. **Load Models**: From registry (1d and 5d)
2. **Raw Predictions**: Get probabilities from trained models
3. **Calibration**: Fit isotonic regression on VAL, apply to TEST
4. **Threshold Tuning**: Optimize confidence/margin gates on VAL
5. **Gating**: Apply confidence thresholds to reduce false trades
6. **Storage**: Save to Supabase and/or Parquet
7. **Reporting**: Generate comparison reports

## Quick Start

### 1. Apply Database Migration

```sql
-- Run in Supabase SQL Editor
-- File: migrations/013_model_predictions_classification.sql
```

### 2. Run Predictions for Both Horizons

```bash
# Process all models for both horizons
python -m ml.src.predict.predict_and_store \
    --horizon all \
    --data_source csv \
    --csv_path_1d classification_dataset.csv \
    --csv_path_5d classification_dataset_5d.csv \
    --store_db

# Process single horizon
python -m ml.src.predict.predict_and_store \
    --horizon 5d \
    --model random_forest \
    --data_source csv \
    --csv_path_5d classification_dataset_5d.csv
```

### 3. Generate Comparison Report

```bash
python ml/src/predict/generate_report.py
```

## Command Line Options

| Flag | Description | Default |
|------|-------------|---------|
| `--horizon` | Prediction horizon: `1d`, `5d`, or `all` | `all` |
| `--model` | Model name or `all` | `all` |
| `--data_source` | Data source: `csv` or `supabase` | `csv` |
| `--csv_path_1d` | Path to 1d CSV | `classification_dataset.csv` |
| `--csv_path_5d` | Path to 5d CSV | `classification_dataset_5d.csv` |
| `--store_db` | Store predictions in Supabase | `False` |
| `--recalibrate` | Force recalibration | `False` |
| `--retune` | Force threshold retuning | `False` |

## Outputs

### Directory Structure

```
ml/artifacts/
├── calibrators/
│   ├── 1d/
│   │   ├── random_forest_ovr.joblib
│   │   ├── lightgbm_ovr.joblib
│   │   └── xgboost_ovr.joblib
│   └── 5d/
│       ├── random_forest_ovr.joblib
│       ├── lightgbm_ovr.joblib
│       └── xgboost_ovr.joblib
├── thresholds/
│   ├── 1d/
│   │   ├── random_forest.json
│   │   ├── lightgbm.json
│   │   └── xgboost.json
│   └── 5d/
│       ├── random_forest.json
│       ├── lightgbm.json
│       └── xgboost.json
├── reports/
│   ├── 1d/
│   │   ├── preds_random_forest_val.parquet
│   │   ├── preds_random_forest_test.parquet
│   │   └── ...
│   ├── 5d/
│   │   ├── preds_random_forest_val.parquet
│   │   ├── preds_random_forest_test.parquet
│   │   └── ...
│   ├── summary_by_horizon.csv
│   └── summary_by_horizon.md
```

### Parquet Schema

Each prediction parquet contains:
- `symbol`: Stock symbol
- `date`: Trading date
- `horizon`: '1d' or '5d'
- `model_name`: Model identifier
- `split`: 'val' or 'test'
- `y_true`: True label {-1, 0, 1}
- `pred_class_raw`: Raw prediction (argmax)
- `pred_class_final`: After confidence gating
- `p_sell`, `p_hold`, `p_buy`: Calibrated probabilities
- `confidence`: Max probability
- `margin`: Top1 - Top2 probability

### Database Schema

Table: `model_predictions_classification`
- Stores all predictions with same schema as Parquet
- Indexed on (symbol, date, horizon, model_name, split)
- Upserts on conflict

## Calibration

**Method**: One-vs-Rest Isotonic Regression
- Fit 3 separate calibrators (one per class)
- Calibrate on VAL split only
- Apply to both VAL and TEST
- Renormalize probabilities to sum to 1

**Metrics**: Brier score per class (before/after)

## Threshold Tuning

**Objective**: Maximize F1 scores while maintaining reasonable trade rates

**Search Space**:
- Confidence: [0.34, 0.75], step 0.01
- Margin: [0.00, 0.35], step 0.01

**Constraints**:
- 1d: Trade rate ∈ [20%, 70%]
- 5d: Trade rate ∈ [15%, 60%]

**Scoring**: 0.6 * F1_macro + 0.4 * F1_action

## Gating Logic

```python
if pred_class_raw == 0:
    pred_class_final = 0  # Always keep Hold
else:
    if confidence >= conf_thresh AND margin >= margin_thresh:
        pred_class_final = pred_class_raw  # High confidence trade
    else:
        pred_class_final = 0  # Low confidence → Hold
```

## Time-Series Safety

✅ **No Leakage**:
- Calibrators fit on VAL only
- Thresholds tuned on VAL only
- TEST never used for any fitting/tuning

✅ **Chronological Splits**:
- Train: 2000-2023
- Val: 2024
- Test: 2025

## Model Registry

Edit `ml/config/model_registry.yaml` to add/remove models:

```yaml
horizons:
  1d:
    target_col: y_class_1d
    models:
      - name: random_forest
        path: ml/artifacts/models/random_forest/model.pkl
        preprocessor_path: ml/artifacts/models/random_forest/preprocessor.pkl
```

## Troubleshooting

**Issue**: "Model not found"
- Check paths in model_registry.yaml
- Ensure models are trained for both horizons

**Issue**: "No thresholds found within constraints"
- Trade rate constraints may be too tight
- Try widening ranges in decision.py

**Issue**: "Probabilities don't sum to 1"
- Check calibration renormalization
- Verify model outputs 3 classes

**Issue**: "Database connection failed"
- Check SUPABASE_URL and SUPABASE_KEY env vars
- Verify migration 013 was applied

## Next Steps

1. **Hyperparameter Tuning**: Optimize models for each horizon
2. **Ensemble**: Combine 1d and 5d predictions
3. **Live Predictions**: Add `split='live'` for real-time inference
4. **Backtesting**: Use stored predictions for strategy simulation
