# Dataset Optimization v2.0 - Change Summary

**Date:** December 13, 2025  
**Objective:** Optimize regression dataset for generalization and stability

---

## 📦 DELIVERABLES

### 1. SQL Migration
- **File:** `migrations/007_optimize_regression_dataset.sql`
- **Purpose:** Database schema updates, views, validation functions
- **Key additions:**
  - `primary_target`, `y_1d_vol_clip`, `y_5d_vol_clip` columns
  - `feature_exclusions` table (12 redundant features)
  - `v_regression_dataset_optimized` view (modeling-ready)
  - `v_regression_diagnostics` view (all targets)
  - `v_feature_manifest` view (documentation)
  - `validate_regression_dataset()` SQL function

### 2. Updated Feature Transform
- **File:** `etl/transform_features.py`
- **Changes:**
  - Fixed `overnight_share` formula (numerical stability)
  - Updated feature manifest comments (83 features)
  - Documented excluded features

### 3. Updated Target Computation
- **File:** `etl/transform_labels.py`
- **Changes:**
  - Added `primary_target`, `y_1d_vol_clip`, `y_5d_vol_clip`
  - Updated docstrings for v2.0
  - Reordered columns (primary targets first)

### 4. Updated Database Loader
- **File:** `etl/load_db.py`
- **Changes:**
  - Updated `upsert_labels()` to handle new columns
  - Reordered row tuple (primary targets first)

### 5. Updated Supabase Client
- **File:** `etl/supabase_client.py`
- **Changes:**
  - Updated `upsert_labels_daily()` to handle new columns
  - Updated row format comments

### 6. New Normalization Module
- **File:** `etl/transform_normalization.py`
- **Purpose:** Feature normalization and clipping utilities
- **Functions:**
  - `zscore_rolling()` - rolling z-score normalization
  - `clip_feature()` - apply clipping thresholds
  - `normalize_features()` - full normalization pipeline
  - `validate_feature_distributions()` - check feature health
  - `apply_feature_clipping()` - clip feature JSON
- **Constants:**
  - `BINARY_FEATURES` - features to skip normalization
  - `VOLATILITY_SCALED_FEATURES` - already normalized
  - `DEFAULT_CLIP_RULES` - clipping thresholds per feature

### 7. New Validation Script
- **File:** `validate_regression_dataset.py`
- **Purpose:** Automated dataset quality checks
- **Validations:**
  - No NaN in primary target (after warm-up)
  - No duplicates
  - Target variance > 0 per symbol
  - Feature count matches expected (83)
  - No extreme outliers
  - Date range sufficient
  - Feature distributions reasonable
- **Usage:** `python validate_regression_dataset.py --supabase`

### 8. Documentation
- **File:** `OPTIMIZATION_SUMMARY.md`
- **Content:** Complete optimization explanation (targets, features, normalization, usage)
  
- **File:** `OPTIMIZATION_QUICK_REF.md`
- **Content:** Quick reference card (cheat sheet for daily use)

---

## 🎯 TARGET OPTIMIZATION

### Primary Target Designated
- **Name:** `primary_target` (alias for `y_1d_vol_clip`)
- **Formula:** `clip(log_return_1d / vol_20, -3, 3)`
- **Benefits:**
  - Volatility-scaled (heteroskedasticity adjustment)
  - Outlier-robust (±3σ clipping)
  - Single recommended target (prevents model selection bias)

### All Targets Available
| Target | Type | Use |
|--------|------|-----|
| `primary_target` | Regression | **DEFAULT** |
| `y_1d_vol_clip` | Regression | PRIMARY (1d) |
| `y_5d_vol_clip` | Regression | SECONDARY (5d) |
| `y_1d_raw` | Regression | Diagnostic |
| `y_5d_raw` | Regression | Diagnostic |
| `y_1d_vol` | Regression | Diagnostic |
| `y_5d_vol` | Regression | Diagnostic |
| `y_1d_clipped` | Regression | Diagnostic |
| `y_5d_clipped` | Regression | Diagnostic |
| `y_1d_class` | Classification | Legacy |
| `y_5d_class` | Classification | Legacy |
| `y_thresh_class` | Classification | Legacy |

---

## 🔧 FEATURE STABILITY FIXES

### 1. overnight_share Formula (CRITICAL)

**Problem:** Division by near-zero returns caused explosions to ±infinity

**Old (unstable):**
```python
overnight_share = overnight_return / (abs(total_return) + 1e-9)
overnight_share = clip(overnight_share, -5, 5)
```

**New (stable):**
```python
total_movement = abs(overnight_return) + abs(intraday_return) + 1e-6
overnight_share = overnight_return / total_movement
overnight_share = clip(overnight_share, -1, 1)
```

**Benefits:**
- Bounded to [-1, 1] by construction
- No explosions when returns are small
- Interpretable ratio of overnight contribution

### 2. Feature Clipping

Applied principled clipping thresholds:
- Continuous (z-scored): ±5σ
- Volatility-scaled: ±3σ
- Correlations: [-1, 1]
- RSI, ADX: [0, 100]
- Drawdown: [-1, 0]
- overnight_share: [-1, 1]

---

## 📉 REDUNDANCY REDUCTION

### Features REMOVED (12)

| Feature | Reason | Alternative |
|---------|--------|-------------|
| `dgs10_change_1d` | Correlated with `dgs10_change_5d` | Use `dgs10_change_5d` |
| `macd_line` | Redundant with `macd_hist` | Use `macd_hist` |
| `macd_signal` | Redundant with `macd_hist` | Use `macd_hist` |
| `sma_5`, `sma_10` | Redundant with `sma_20` | Use `sma_20/50/200` |
| `ema_5`, `ema_10` | Redundant with `ema_20` | Use `ema_20/50` |
| `ema_200` | Redundant with `sma_200` | Use `sma_200` |
| `log_ret_10d` | Redundant with `log_ret_5d/20d` | Use `log_ret_5d/20d` |
| `vol_10` | Redundant with `vol_5/20/60` | Use `vol_5/20/60` |
| `dd_20` | Redundant with `dd_60` | Use `dd_60` |
| `obv` | Noisy, redundant with `volume_z` | Use `volume_z` |

**Impact:**
- ✓ Reduced multicollinearity
- ✓ More stable model coefficients
- ✓ Faster training
- ✓ Easier interpretation

### Features KEPT (83)

See `OPTIMIZATION_SUMMARY.md` for complete list.

**Categories:**
- Technical: 22
- Overnight/Intraday: 7
- Trend Quality: 3
- Macro: 11
- VIX: 4
- Cross-Asset: 8
- Breadth: 4
- Lagged: 8
- Regime: 4
- Events: 3

---

## 📏 NORMALIZATION STRATEGY

### Rolling Z-Score Per Symbol

**Method:**
```python
zscore = (x - rolling_mean_252) / rolling_std_252
clipped = clip(zscore, -5, 5)
```

**Why:**
- Prevents look-ahead bias (only uses past data)
- Adapts to regime changes
- Per-symbol fairness (different vol profiles)

**Excluded:**
- Binary features (regime flags, events)
- Already-bounded features (RSI, ADX, correlations)

---

## 🗄️ DATABASE VIEWS

### v_regression_dataset_optimized
- **Purpose:** Ready-to-use modeling dataset
- **Contents:** Primary target + 83 features
- **Filter:** Only rows with valid targets

### v_regression_diagnostics
- **Purpose:** Compare all target variants
- **Contents:** All 9 regression targets + variance metrics

### v_feature_manifest
- **Purpose:** Feature documentation
- **Contents:** Name, type, description, scaling rules, exclusions

### v_optimization_summary
- **Purpose:** Quick summary of changes
- **Contents:** Target info, feature counts, date range

---

## ✅ VALIDATION FRAMEWORK

### Automated Checks

1. ✓ No NaN in primary_target (after warm-up)
2. ✓ No duplicate (symbol, date)
3. ✓ Target variance > 0 per symbol
4. ✓ Feature count = 83
5. ✓ No extreme outliers
6. ✓ Date range ≥ 10 years
7. ✓ Feature distributions reasonable

### Run Validation

```bash
# Python script
python validate_regression_dataset.py --supabase

# SQL function
select * from public.validate_regression_dataset();
```

---

## 🚀 DEPLOYMENT

### Step 1: Run Migration
```bash
psql $DATABASE_URL -f migrations/007_optimize_regression_dataset.sql
```

### Step 2: Backfill Data
```bash
python -m etl.main --start 2000-01-01 --end 2025-12-13 --mode backfill
```

This will:
- Recalculate `overnight_share` with stable formula
- Populate new target columns
- Set `primary_target` for all valid rows

### Step 3: Validate
```bash
python validate_regression_dataset.py --supabase
```

Expected: All checks pass (7 passed, 0 failed)

---

## 📊 USAGE EXAMPLE

```python
from etl.supabase_client import SupabaseDB
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import Ridge

# Load optimized dataset
db = SupabaseDB(url=SUPABASE_URL, key=SUPABASE_KEY)
df = db.query_to_dataframe("""
    select * from public.v_regression_dataset_optimized
    where symbol = 'SPY'
    order by date
""")

# Prepare features and target
feature_cols = [c for c in df.columns 
                if c not in ['symbol', 'date', 'primary_target']]
X, y = df[feature_cols], df['primary_target']

# Walk-forward validation
tscv = TimeSeriesSplit(n_splits=5)
model = Ridge(alpha=1.0)

for train_idx, test_idx in tscv.split(X):
    model.fit(X.iloc[train_idx], y.iloc[train_idx])
    score = model.score(X.iloc[test_idx], y.iloc[test_idx])
    print(f"R² = {score:.4f}")
```

---

## 📁 FILES CHANGED

### New Files (4)
1. `migrations/007_optimize_regression_dataset.sql`
2. `etl/transform_normalization.py`
3. `validate_regression_dataset.py`
4. `OPTIMIZATION_SUMMARY.md`
5. `OPTIMIZATION_QUICK_REF.md`
6. `DATASET_OPTIMIZATION_CHANGELOG.md` (this file)

### Modified Files (5)
1. `etl/transform_features.py`
2. `etl/transform_labels.py`
3. `etl/load_db.py`
4. `etl/supabase_client.py`

### No Changes Required
- `etl/extract_*.py` (data sources unchanged)
- `etl/transform_features_context.py` (merge logic unchanged)
- `etl/transform_lags.py` (lag computation unchanged)
- `etl/transform_regimes.py` (regime flags unchanged)

---

## 🎯 KEY ACHIEVEMENTS

✅ **Target Standardization:** Single primary target (`primary_target`)  
✅ **Numerical Stability:** Fixed `overnight_share` explosions  
✅ **Redundancy Reduction:** 12 features removed, 83 kept  
✅ **Outlier Robustness:** Principled clipping rules applied  
✅ **Validation Framework:** Automated health checks  
✅ **Documentation:** Complete usage guide and quick reference  

---

## 📚 REFERENCES

**Documentation:**
- `OPTIMIZATION_SUMMARY.md` - Full details
- `OPTIMIZATION_QUICK_REF.md` - Quick reference
- `FEATURE_MANIFEST.md` - Feature definitions
- `REGRESSION_SUMMARY.md` - Previous regression work

**Code:**
- `etl/transform_*.py` - Feature engineering
- `etl/load_db.py` - Database loading
- `validate_regression_dataset.py` - Validation

**Database:**
- `migrations/007_optimize_regression_dataset.sql` - Schema
- `v_regression_dataset_optimized` - Modeling view
- `v_feature_manifest` - Feature metadata

---

**Version:** 2.0 (Optimized)  
**Status:** ✅ Complete and ready for deployment  
**Last Updated:** December 13, 2025
