# Regression Dataset Optimization - Quick Reference

## 🎯 PRIMARY TARGET

**Use this:** `primary_target` (alias for `y_1d_vol_clip`)

**Formula:** `clip(log_return_1d / vol_20, -3, 3)`

**Why:** Volatility-scaled + outlier-robust + proven generalization

---

## 📊 DATASET ACCESS

### SQL (Supabase)
```sql
-- Modeling dataset (ready to use)
select * from public.v_regression_dataset_optimized
where symbol = 'SPY' and date >= '2010-01-01'
order by date;

-- All targets for comparison
select * from public.v_regression_diagnostics
where symbol = 'SPY';

-- Feature metadata
select * from public.v_feature_manifest
where is_excluded = false;
```

### Python
```python
from etl.supabase_client import SupabaseDB

db = SupabaseDB(url=SUPABASE_URL, key=SUPABASE_KEY)
df = db.query_to_dataframe(
    "select * from public.v_regression_dataset_optimized"
)
```

---

## ✨ KEY FEATURES (83 total)

### Technical (22)
Returns, volatility, momentum, volume, moving averages, drawdown

### Overnight/Intraday (7)
Gap behavior, intraday movement, overnight_share (FIXED)

### Trend Quality (3)
ADX, return autocorrelation, R² of price vs time

### Macro (11)
Rates, credit spreads, Fed liquidity, yield curve

### VIX (4)
Level, changes, term structure

### Cross-Asset (8)
Dollar, gold, oil, bonds, high-yield

### Breadth (4)
Equal-weight vs cap-weight ratios

### Lagged (8)
Returns, VIX, credit, yield curve lags

### Regime (4)
High vol, inverted curve, credit stress, liquidity

### Events (3)
FOMC, CPI, NFP

---

## 🔧 FEATURES REMOVED (12)

- `dgs10_change_1d` → use `dgs10_change_5d`
- `macd_line`, `macd_signal` → use `macd_hist`
- `sma_5/10`, `ema_5/10/200` → redundant with kept MAs
- `log_ret_10d`, `vol_10`, `dd_20` → redundant windows
- `obv` → redundant with `volume_z`

**Why:** Reduce collinearity, improve stability

---

## 📏 NORMALIZATION

### Apply per symbol:
```python
from etl.transform_normalization import normalize_features

df_norm = df.groupby('symbol', group_keys=False).apply(
    lambda g: normalize_features(g, window=252, clip_continuous=5.0)
)
```

### Rules:
- **Continuous features:** Z-score (252-day rolling) + clip to ±5
- **Binary features:** No transformation
- **Vol-scaled features:** Already normalized

---

## ✅ VALIDATION

```bash
# Check dataset health
python validate_regression_dataset.py --supabase
```

**Checks:**
- No NaN in primary_target (after 252-day warm-up)
- No duplicates
- Target variance > 0 per symbol
- 83 features present
- No extreme outliers
- 10+ years of data

---

## 🚀 DEPLOYMENT STEPS

```bash
# 1. Run migration
psql $DATABASE_URL -f migrations/007_optimize_regression_dataset.sql

# 2. Backfill data (updates overnight_share, adds new targets)
python -m etl.main --start 2000-01-01 --end 2025-12-13 --mode backfill

# 3. Validate
python validate_regression_dataset.py --supabase
```

---

## 📝 EXAMPLE: BASIC MODEL

```python
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import Ridge
from etl.supabase_client import SupabaseDB

# Load data
db = SupabaseDB(url=SUPABASE_URL, key=SUPABASE_KEY)
df = db.query_to_dataframe("""
    select * from public.v_regression_dataset_optimized
    where symbol = 'SPY'
    order by date
""")

# Prepare features
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

## 🔍 KEY FIXES

### 1. overnight_share (numerical stability)
**Old:** `overnight_return / abs(total_return)`  
**New:** `overnight_return / (abs(overnight) + abs(intraday) + ε)`  
**Result:** Bounded to [-1, 1], no explosions

### 2. Primary target (standardization)
**Before:** Multiple targets, unclear default  
**After:** `primary_target` = single recommended target  
**Result:** Consistent modeling approach

### 3. Redundant features (collinearity)
**Before:** 95 features, many correlated  
**After:** 83 features, reduced multicollinearity  
**Result:** More stable models

---

## 📚 DOCUMENTATION

- **Full details:** `OPTIMIZATION_SUMMARY.md`
- **Features:** `FEATURE_MANIFEST.md`
- **Validation:** `validate_regression_dataset.py`
- **Views:** `v_regression_dataset_optimized`, `v_feature_manifest`

---

## 🎓 BEST PRACTICES

1. **Always use primary_target** for consistency
2. **Apply rolling normalization** per symbol
3. **Use walk-forward validation** (TimeSeriesSplit)
4. **Monitor feature drift** over time
5. **Validate data** before training
6. **Clip predictions** to reasonable range

---

**Version:** 2.0 (Optimized)  
**Date:** December 13, 2025  
**Status:** Ready for production modeling
