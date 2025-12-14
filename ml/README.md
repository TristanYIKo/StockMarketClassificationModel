# ML Training Pipeline - Stock Market Classification

Complete ML training pipeline for stock market classification with strict time-series safety.

## Overview

Trains 4 models to predict next-day price movements:
- **Logistic Regression** (baseline)
- **Random Forest**
- **LightGBM**
- **XGBoost**

Target: `y_class_1d` from triple-barrier method
- `-1` = Sell (price moves down significantly)
- `0` = Hold (price stays within range)
- `1` = Buy (price moves up significantly)

## Key Features

✅ **Time-series safe evaluation** - No random splits, chronological only  
✅ **No data leakage** - Preprocessing fit only on training data  
✅ **Class imbalance handling** - Balanced class weights  
✅ **Comprehensive metrics** - Accuracy, F1, precision/recall per class  
✅ **Confusion matrices** - Visual evaluation of predictions  
✅ **Model comparison** - Side-by-side performance comparison  

## Project Structure

```
ml/
├── config/
│   └── model_config.yaml          # Training configuration
├── data/
│   ├── raw/                        # Original CSV/exports
│   └── processed/                  # Preprocessed data (optional)
├── src/
│   ├── utils/
│   │   ├── io.py                  # Data loading (CSV/Supabase)
│   │   ├── splits.py              # Time-based train/val/test splits
│   │   ├── preprocess.py          # Preprocessing pipeline
│   │   └── metrics.py             # Evaluation metrics
│   └── train/
│       └── train_models.py        # Main training script
├── artifacts/
│   ├── models/                     # Saved models + preprocessors
│   ├── figures/                    # Confusion matrices, comparisons
│   ├── reports/                    # Performance reports
│   └── training.log                # Training logs
├── notebooks/                      # Jupyter notebooks for exploration
└── requirements.txt                # Python dependencies
```

## Quick Start

### 1. Install Dependencies

```bash
cd ml
pip install -r requirements.txt
```

### 2. Train Models (CSV)

```bash
python -m src.train.train_models --data_source csv --csv_path ../classification_dataset.csv
```

### 3. Train Models (Supabase)

Set environment variables:
```bash
export SUPABASE_URL="your-url"
export SUPABASE_KEY="your-key"
```

Then run:
```bash
python -m src.train.train_models --data_source supabase
```

## Configuration

Edit `config/model_config.yaml` to customize:

- **Time splits** - Train/val/test date ranges
- **Preprocessing** - Missing value threshold, imputation strategy, scaling
- **Model hyperparameters** - n_estimators, learning_rate, max_depth, etc.

Example:
```yaml
data:
  train_start: "2000-02-01"
  train_end: "2023-12-31"
  val_start: "2024-01-01"
  val_end: "2024-12-31"
  test_start: "2025-01-01"
  test_end: "2025-01-31"

preprocessing:
  drop_features_threshold: 0.30  # Drop features >30% missing
  imputation_strategy: "median"
  scaling: true
```

## Output

After training, artifacts are saved to `ml/artifacts/`:

### Models
- `models/<model_name>/model.pkl` - Trained model
- `models/<model_name>/preprocessor.pkl` - Fitted preprocessor
- `models/<model_name>/metadata.json` - Config + metrics

### Figures
- `figures/confusion_matrix_train.png` - Training confusion matrix
- `figures/confusion_matrix_val.png` - Validation confusion matrix
- `figures/confusion_matrix_test.png` - Test confusion matrix
- `figures/model_comparison.png` - Model performance comparison

### Logs
- `training.log` - Complete training log with metrics

## Time-Series Safety

**CRITICAL**: All splits are chronological:
- Train: 2000-2023 (historical data)
- Val: 2024 (recent past)
- Test: 2025 (future unseen data)

**No random sampling**. Preprocessing (imputers, scalers) fit ONLY on training data.

## Data Requirements

Input CSV must have:
- `symbol` - Stock ticker
- `date` - Trading date
- `y_class_1d` - Target label (-1, 0, or 1)
- Feature columns (117 features)

## Model Evaluation

Each model evaluated on:
- **Accuracy** - Overall correctness
- **F1 (macro)** - Unweighted average F1 across classes
- **F1 (weighted)** - Weighted by class support
- **Precision/Recall** - Per-class performance
- **Confusion Matrix** - Detailed prediction breakdown

## Common Issues

### Missing Values
Features with >30% missing in training set are dropped. Remaining missing values imputed with median (default).

### Class Imbalance
`class_weight='balanced'` automatically adjusts for imbalanced classes (Hold is only ~22%).

### Memory Issues
If dataset is too large, preprocess and save to parquet:
```python
from src.utils.io import load_from_csv, save_to_parquet
df = load_from_csv('classification_dataset.csv')
save_to_parquet(df, 'data/processed/dataset.parquet')
```

## Next Steps

After training:
1. Review model comparison in `artifacts/figures/model_comparison.png`
2. Analyze confusion matrices to understand error patterns
3. Select best model based on validation F1 (macro)
4. Use best model for backtesting/trading strategy
5. Monitor test performance to check generalization

## Example Output

```
======================================================================
MODEL COMPARISON
======================================================================
                    train_accuracy  val_accuracy  test_accuracy  train_f1_macro  val_f1_macro  test_f1_macro
xgboost                     0.9876        0.5432         0.5234          0.9845        0.5123        0.4987
lightgbm                    0.9823        0.5398         0.5198          0.9801        0.5089        0.4945
random_forest               0.9765        0.5301         0.5087          0.9734        0.4987        0.4823
logistic_regression         0.5987        0.4987         0.4876          0.5876        0.4765        0.4654
======================================================================
```

## Support

For issues or questions:
1. Check `training.log` for detailed error messages
2. Verify data format matches requirements
3. Review config file for correct date ranges
4. Ensure all dependencies installed correctly
