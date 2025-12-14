# Regression Dataset Optimization Summary

**Date:** December 13, 2025  
**Version:** 2.0 (Optimized)  
**Objective:** Optimize dataset for generalization, numerical stability, and signal efficiency

---

## Overview

This optimization focuses on **preparing an existing strong dataset** for robust walk-forward regression modeling. No new data sources were added. Changes target:

1. **Target standardization** - Single primary regression target
2. **Feature stability** - Fixed numerically unstable calculations
3. **Redundancy reduction** - Removed collinear features
4. **Outlier robustness** - Applied principled clipping
5. **Validation framework** - Automated quality checks

---

## A) Target Optimization (CRITICAL)

### Primary Regression Target

**Selected:** `y_1d_vol_clip` (volatility-scaled + clipped 1-day return)

**Why:**
- **Volatility-scaled**: Divides raw return by 20-day realized volatility → stabilizes variance across time (heteroskedasticity adjustment)
- **Clipped to ±3σ**: Removes extreme outliers while preserving signal
- **1-day horizon**: Balances signal quality vs noise (5-day secondary target available)

**Formula:**
```python
y_1d_vol_clip = clip(log_return_1d / vol_20, -3, 3)
```

### All Targets Available

| Target | Type | Use Case |
|--------|------|----------|
| `primary_target` | Regression | **Default for modeling** (alias for y_1d_vol_clip) |
| `y_1d_vol_clip` | Regression | PRIMARY: 1d vol-scaled + clipped |
| `y_5d_vol_clip` | Regression | SECONDARY: 5d vol-scaled + clipped |
| `y_1d_raw` | Regression | Diagnostic: raw log return |
| `y_5d_raw` | Regression | Diagnostic: raw log return |
| `y_1d_vol` | Regression | Diagnostic: vol-scaled (unclipped) |
| `y_5d_vol` | Regression | Diagnostic: vol-scaled (unclipped) |
| `y_1d_clipped` | Regression | Diagnostic: clipped raw return |
| `y_5d_clipped` | Regression | Diagnostic: clipped raw return |
| `y_1d_class` | Classification | Legacy: binary up/down |
| `y_5d_class` | Classification | Legacy: binary up/down |
| `y_thresh_class` | Classification | Legacy: threshold-based |

**Recommendation:** Use `primary_target` for all training unless experimenting with alternatives.

---

## B) Feature Stability Fixes

### 1. overnight_share Formula Update

**Problem:** Original formula was numerically unstable:
```python
# OLD (unstable)
overnight_share = overnight_return / (abs(total_return) + epsilon)
```

When `total_return ≈ 0`, ratio explodes to ±infinity despite overnight return also being small.

**Solution:** Normalize by total movement (sum of absolute components):
```python
# NEW (stable)
overnight_share = overnight_return / (abs(overnight_return) + abs(intraday_return) + 1e-6)
overnight_share = clip(overnight_share, -1, 1)
```

**Benefits:**
- Bounded to [-1, 1] by construction
- Handles near-zero returns gracefully
- Interpretable: ratio of overnight contribution to total movement

### 2. Feature Clipping Rules

Applied principled clipping to prevent outliers from destabilizing models:

| Feature Type | Clipping Rule | Rationale |
|-------------|---------------|-----------|
| Continuous (z-scored) | ±5σ | Beyond 5σ is likely noise or data error |
| Volatility-scaled | ±3σ | Already variance-normalized |
| Correlations | [-1, 1] | Natural bounds |
| RSI, ADX | [0, 100] | Bounded by design |
| Drawdown | [-1, 0] | Natural bounds |
| overnight_share | [-1, 1] | Bounded ratio |

---

## C) Redundancy & Collinearity Reduction

### Features REMOVED (12 total)

Removed highly correlated or redundant features to improve model generalization:

| Feature | Reason | Kept Alternative |
|---------|--------|------------------|
| `dgs10_change_1d` | Highly correlated with `dgs10_change_5d` | `dgs10_change_5d`, `yield_curve_slope` |
| `macd_line` | Redundant with `macd_hist` | `macd_hist` only |
| `macd_signal` | Redundant with `macd_hist` | `macd_hist` only |
| `sma_5`, `sma_10` | Too short, redundant with `sma_20` | `sma_20`, `sma_50`, `sma_200` |
| `ema_5`, `ema_10` | Too short, redundant with `ema_20` | `ema_20`, `ema_50` |
| `ema_200` | Highly correlated with `sma_200` | `sma_200`, `ema_50` |
| `log_ret_10d` | Redundant with 5d/20d | `log_ret_5d`, `log_ret_20d` |
| `vol_10` | Redundant with 5/20/60 | `vol_5`, `vol_20`, `vol_60` |
| `dd_20` | Redundant with `dd_60` | `dd_60` |
| `obv` | Noisy, redundant with `volume_z` | `volume_z`, `volume_chg_pct` |

**Impact:**
- Reduced multicollinearity → more stable coefficients
- Faster training
- Easier interpretation

### Features KEPT (83 total)

**Technical (22):**
- Returns: `log_ret_1d`, `log_ret_5d`, `log_ret_20d`
- Momentum: `rsi_14`, `macd_hist`
- Volatility: `vol_5`, `vol_20`, `vol_60`, `atr_14`
- Range: `high_low_pct`, `close_open_pct`
- Moving Averages: `sma_20`, `sma_50`, `sma_200`, `ema_20`, `ema_50`, `sma20_gt_sma50`
- Volume: `volume_z`, `volume_chg_pct`
- Drawdown: `dd_60`
- Calendar: `dow`, `days_since_prev`

**Overnight/Intraday (7):**
- `overnight_return`, `intraday_return`
- `overnight_mean_20`, `overnight_std_20`
- `intraday_mean_20`, `intraday_std_20`
- `overnight_share` (FIXED)

**Trend Quality (3):**
- `adx_14` (trend strength)
- `return_autocorr_20` (momentum vs mean reversion)
- `price_rsq_20` (linear trend fit quality)

**Macro (11):**
- Rates: `dgs2`, `dgs10`, `yield_curve_slope`, `dgs10_change_5d`
- Credit: `hy_oas_level`, `hy_oas_change_1d`, `hy_oas_change_5d`
- Liquidity: `liquidity_expanding`, `fed_bs_chg_pct`, `rrp_level`, `rrp_chg_pct_5d`

**VIX (4):**
- `vix_level`, `vix_change_1d`, `vix_change_5d`, `vix_term_structure`

**Cross-Asset (8):**
- `dxy_ret_5d`, `gold_ret_5d`, `oil_ret_5d`
- `hyg_ret_5d`, `hyg_vs_spy_5d`, `hyg_spy_corr_20d`
- `lqd_ret_5d`, `tlt_ret_5d`

**Breadth (4):**
- `rsp_spy_ratio`, `rsp_spy_ratio_z`
- `qqq_spy_ratio_z`, `iwm_spy_ratio_z`

**Lagged Features (8):**
- `log_ret_1d_lag1/2/3/5`
- `vix_change_lag1/3`
- `hy_oas_change_lag1`
- `yield_curve_slope_lag1`

**Regime Flags (4):**
- `high_vol_regime` (VIX > 20 OR > 75th percentile)
- `curve_inverted` (DGS10 < DGS2)
- `credit_stress` (HY OAS > 80th percentile)
- `liquidity_expanding_regime` (Fed BS 4-week change > 0)

**Event Flags (3):**
- `is_fomc`, `is_cpi_release`, `is_nfp_release`

---

## D) Feature Normalization Strategy

### Per-Symbol Rolling Z-Score

**Method:**
```python
zscore = (x - rolling_mean_252) / rolling_std_252
clipped = clip(zscore, -5, 5)
```

**Why rolling window:**
- Prevents look-ahead bias (only uses past data)
- Adapts to regime changes (2008 crisis, COVID, etc.)
- Per-symbol normalization handles different volatility profiles

**Excluded from scaling:**
- Binary features (regime flags, events, dow)
- Already-bounded features (RSI, ADX, correlations)

**Implementation:**
```python
from etl.transform_normalization import normalize_features

df_normalized = normalize_features(
    features_df,
    window=252,  # 1 trading year
    clip_continuous=5.0
)
```

---

## E) Regime & Event Handling

**No changes.** Existing implementation is sound:

**Regime Flags (kept as-is):**
- `high_vol_regime`: VIX > 20 OR VIX > 75th percentile (60d)
- `curve_inverted`: DGS10 < DGS2
- `credit_stress`: HY OAS > 80th percentile (60d)
- `liquidity_expanding_regime`: Fed BS 4-week change > 0

**Event Flags (kept as-is):**
- `is_fomc`: FOMC meeting date (8/year)
- `is_cpi_release`: CPI release date (12/year)
- `is_nfp_release`: NFP jobs report date (12/year, first Friday)

**Rationale:** These are high-ROI features with clear economic interpretation.

---

## F) Dataset Health & Validation

### Automated Validation Checks

Created `validate_regression_dataset.py` with checks:

1. **No NaN in primary_target** (beyond 252-day warm-up)
2. **No duplicate (symbol, date)** pairs
3. **Target variance > 0** per symbol
4. **Feature count** matches expected (83)
5. **No extreme outliers** beyond clipping thresholds
6. **Date range** sufficient (10+ years)
7. **Feature distributions** reasonable (not excessive nulls or outliers)

**Usage:**
```bash
python validate_regression_dataset.py --supabase
```

### SQL Validation Function

Added to database:
```sql
select * from public.validate_regression_dataset();
```

Returns table with check results:
- `check_name`: Validation test name
- `status`: PASS / FAIL / WARN
- `details`: Diagnostic message

---

## G) Output Datasets

### 1. Optimized Modeling Dataset

**View:** `public.v_regression_dataset_optimized`

**Contents:**
- Primary target only (`primary_target`)
- 83 non-redundant features
- Rows with valid targets only
- Ready for train/test split

**SQL:**
```sql
select * from public.v_regression_dataset_optimized
where symbol = 'SPY'
  and date >= '2010-01-01'
order by date;
```

**Python:**
```python
from etl.supabase_client import SupabaseDB

db = SupabaseDB(url=SUPABASE_URL, key=SUPABASE_KEY)
query = "select * from public.v_regression_dataset_optimized"
df = db.query_to_dataframe(query)
```

### 2. Diagnostics Dataset

**View:** `public.v_regression_diagnostics`

**Contents:**
- ALL target variants (raw, vol-scaled, clipped, combinations)
- Rolling variance metrics
- For comparing target transformations

**Use case:** Research and experimentation with alternative targets

### 3. Feature Manifest

**View:** `public.v_feature_manifest`

**Contents:**
- Feature name, type, description
- Scaling method, clipping rules
- Exclusion status and reason

**Use case:** Documentation and feature engineering reference

---

## H) Migration & Deployment

### Step 1: Run SQL Migration

```bash
# Connect to Supabase and run migration
psql $DATABASE_URL -f migrations/007_optimize_regression_dataset.sql
```

**What it does:**
- Adds `primary_target`, `y_1d_vol_clip`, `y_5d_vol_clip` columns
- Creates feature exclusion table
- Updates feature metadata with clipping rules
- Creates optimized views
- Adds validation functions

### Step 2: Recompute Features & Targets

```bash
# Backfill with updated feature definitions
python -m etl.main --start 2000-01-01 --end 2025-12-13 --mode backfill
```

**What happens:**
- `overnight_share` recalculated with stable formula
- New target columns populated
- `primary_target` set for all valid rows

### Step 3: Validate Dataset

```bash
# Run validation checks
python validate_regression_dataset.py --supabase
```

Expected output:
```
REGRESSION DATASET VALIDATION REPORT
======================================================================

no_nans                   ✓ No NaN in primary_target after 252-day warm-up
no_duplicates             ✓ No duplicate (symbol, date) pairs
target_variance           ✓ All 4 symbols have non-zero target variance
feature_count             ✓ Feature count matches expected: 83 features
no_extreme_outliers       ✓ No extreme outliers in primary_target
date_range                ✓ Date range: 2000-01-04 to 2025-12-13 (25.9 years)
feature_distributions     ✓ Feature distributions look reasonable

SUMMARY: 7 passed, 0 failed, 0 warnings
```

---

## I) Usage Examples

### Basic Model Training

```python
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import Ridge

# Load optimized dataset
from etl.supabase_client import SupabaseDB

db = SupabaseDB(url=SUPABASE_URL, key=SUPABASE_KEY)
query = """
    select * from public.v_regression_dataset_optimized
    where symbol = 'SPY'
    order by date
"""
df = db.query_to_dataframe(query)

# Feature columns (exclude metadata and target)
feature_cols = [c for c in df.columns 
                if c not in ['symbol', 'date', 'primary_target']]

X = df[feature_cols]
y = df['primary_target']

# Walk-forward validation
tscv = TimeSeriesSplit(n_splits=5)
model = Ridge(alpha=1.0)

for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    
    model.fit(X_train, y_train)
    score = model.score(X_test, y_test)
    print(f"R² = {score:.4f}")
```

### Feature Normalization

```python
from etl.transform_normalization import normalize_features

# Apply rolling z-score normalization per symbol
df_normalized = df.groupby('symbol', group_keys=False).apply(
    lambda g: normalize_features(g, window=252, clip_continuous=5.0)
)
```

### Alternative Target Experimentation

```python
# Compare targets
from etl.supabase_client import SupabaseDB

db = SupabaseDB(url=SUPABASE_URL, key=SUPABASE_KEY)
df_diag = db.query_to_dataframe(
    "select * from public.v_regression_diagnostics where symbol = 'SPY'"
)

# Compare variance stability
print("Target Variance (252-day rolling):")
print(df_diag[['y_1d_raw_std_252', 'y_1d_vol_std_252', 'y_1d_vol_clip_std_252']].mean())
```

---

## J) Key Decisions & Rationale

### Why y_1d_vol_clip as primary target?

1. **Volatility scaling** stabilizes variance across market regimes (2008, COVID, etc.)
2. **Clipping to ±3σ** removes outliers without losing signal
3. **1-day horizon** balances signal strength vs noise
4. **Single target** prevents model selection bias

### Why remove redundant features?

1. **Multicollinearity** → unstable coefficients in linear models
2. **Overfitting risk** → correlated features amplify noise
3. **Faster training** → fewer features = less compute
4. **Easier interpretation** → clearer feature importance

### Why rolling normalization?

1. **Prevents look-ahead bias** (only uses past data)
2. **Adapts to regime changes** (mean/std shift over time)
3. **Per-symbol fairness** (SPY vs IWM have different vol profiles)

### Why keep regime flags as binary?

1. **Interpretability** → clear economic meaning
2. **Non-linearity** → captures threshold effects
3. **No scaling needed** → already 0/1

---

## K) Next Steps

### Immediate
1. ✅ Run migration 007
2. ✅ Backfill data with updated features
3. ✅ Validate dataset
4. ⏳ Train baseline models

### Future Enhancements
- [ ] Add walk-forward CV framework
- [ ] Implement feature selection (LASSO, RFE)
- [ ] Add ensemble models (Ridge + Lasso + ElasticNet)
- [ ] Track model performance over time
- [ ] Add prediction confidence intervals

---

## L) References

**Migrations:**
- `001_init_schema.sql` - Initial schema
- `005_regression_features.sql` - Regression targets
- `007_optimize_regression_dataset.sql` - THIS optimization

**Code Modules:**
- `etl/transform_features.py` - Feature engineering
- `etl/transform_labels.py` - Target computation
- `etl/transform_normalization.py` - Normalization utilities
- `etl/load_db.py` - Database loading
- `validate_regression_dataset.py` - Validation script

**Views:**
- `v_regression_dataset_optimized` - Modeling dataset
- `v_regression_diagnostics` - All targets for comparison
- `v_feature_manifest` - Feature documentation
- `v_optimization_summary` - Change summary

---

## Contact & Questions

For questions about this optimization:
- Review `FEATURE_MANIFEST.md` for feature definitions
- Check `validate_regression_dataset.py` for dataset health
- Query `v_feature_manifest` for metadata
- Run `validate_regression_dataset()` SQL function

**Last Updated:** December 13, 2025
