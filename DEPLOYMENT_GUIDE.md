# Dataset Optimization v2.0 - Deployment Guide

**Status:** ✅ Ready for deployment  
**Date:** December 13, 2025

---

## 🎯 WHAT THIS DOES

Optimizes your regression dataset by:
1. Designating a primary target (`primary_target` = `y_1d_vol_clip`)
2. Fixing `overnight_share` numerical instability
3. Removing 12 redundant features (reduces collinearity)
4. Adding clipping rules for outlier robustness
5. Creating optimized database views
6. Adding automated validation checks

**No new data sources. No data leakage. Pure optimization.**

---

## 📋 PRE-DEPLOYMENT CHECKLIST

- [ ] Supabase credentials available (`$SUPABASE_URL`, `$SUPABASE_KEY`)
- [ ] FRED API key available (`$FRED_API_KEY`)
- [ ] Database backup created (recommended)
- [ ] Python environment activated (`.venv`)
- [ ] Current ETL pipeline working

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Review Changes (Optional)

```bash
# Review SQL migration
cat migrations/007_optimize_regression_dataset.sql

# Review feature changes
git diff etl/transform_features.py
git diff etl/transform_labels.py
```

### Step 2: Run SQL Migration

```bash
# Option A: Using psql (if you have direct database access)
psql $DATABASE_URL -f migrations/007_optimize_regression_dataset.sql

# Option B: Using Supabase SQL Editor
# 1. Open Supabase Dashboard → SQL Editor
# 2. Copy contents of migrations/007_optimize_regression_dataset.sql
# 3. Execute
```

**What this does:**
- Adds new target columns to `labels_daily` table
- Creates `feature_exclusions` table
- Adds feature metadata columns
- Creates optimized views (`v_regression_dataset_optimized`, etc.)
- Adds validation function

**Expected output:**
```
BEGIN
ALTER TABLE
UPDATE
CREATE TABLE
CREATE INDEX
CREATE VIEW
...
COMMIT
```

### Step 3: Backfill Data

```bash
# Set environment variables
export SUPABASE_URL="your_url"
export SUPABASE_KEY="your_key"
export FRED_API_KEY="your_key"

# Or on Windows PowerShell:
$env:SUPABASE_URL = "your_url"
$env:SUPABASE_KEY = "your_key"
$env:FRED_API_KEY = "your_key"

# Run backfill (this will recompute features with updated formulas)
python -m etl.main --start 2000-01-01 --end 2025-12-13 --mode backfill
```

**What this does:**
- Recalculates `overnight_share` with stable formula
- Computes new target columns (`primary_target`, `y_1d_vol_clip`, `y_5d_vol_clip`)
- Updates all existing data with optimized features

**Expected runtime:** 10-30 minutes (depending on date range and data volume)

**Progress indicators:**
```
[INFO] Processing SPY...
[INFO] Computing features...
[INFO] Computing labels...
[INFO] Upserting 6500 rows...
[INFO] Processing QQQ...
...
```

### Step 4: Validate Dataset

```bash
# Run validation checks
python validate_regression_dataset.py --supabase
```

**Expected output (all checks should pass):**
```
======================================================================
REGRESSION DATASET VALIDATION REPORT
======================================================================

no_nans                   ✓ No NaN in primary_target after 252-day warm-up (25000+ rows checked)
no_duplicates             ✓ No duplicate (symbol, date) pairs
target_variance           ✓ All 4 symbols have non-zero target variance
feature_count             ✓ Feature count matches expected: 83 features
no_extreme_outliers       ✓ No extreme outliers in primary_target (all within ±3)
date_range                ✓ Date range: 2000-01-04 to 2025-12-13 (25.9 years)
feature_distributions     ✓ Feature distributions look reasonable (83 features checked)

----------------------------------------------------------------------
SUMMARY: 7 passed, 0 failed, 0 warnings
======================================================================
```

**If any checks fail:**
- Review error messages
- Check database migration completed successfully
- Verify backfill completed without errors
- See "Troubleshooting" section below

---

## ✅ POST-DEPLOYMENT VERIFICATION

### 1. Check Database Views

```sql
-- Count rows in optimized view
select symbol, count(*) as row_count
from public.v_regression_dataset_optimized
group by symbol
order by symbol;

-- Check feature count
select count(*) as feature_count
from information_schema.columns
where table_schema = 'public'
  and table_name = 'v_regression_dataset_optimized'
  and column_name not in ('symbol', 'date', 'primary_target');
-- Should return: 83

-- Sample data
select * from public.v_regression_dataset_optimized
where symbol = 'SPY'
order by date desc
limit 10;
```

### 2. Check Target Distributions

```sql
-- Primary target statistics per symbol
select 
  symbol,
  count(*) as n,
  avg(primary_target) as mean,
  stddev(primary_target) as std,
  min(primary_target) as min,
  max(primary_target) as max
from public.v_regression_dataset_optimized
group by symbol;
```

**Expected:**
- Mean ≈ 0 (small positive bias OK)
- Std ≈ 1.0-1.5 (volatility-scaled)
- Min/Max within ±3.0 (clipped)

### 3. Check overnight_share Bounds

```sql
-- overnight_share should be in [-1, 1]
select 
  symbol,
  min((feature_json->>'overnight_share')::numeric) as min_share,
  max((feature_json->>'overnight_share')::numeric) as max_share
from public.features_daily f
join public.assets a on a.id = f.asset_id
where a.asset_type = 'ETF'
group by symbol;
```

**Expected:** All min/max within [-1, 1]

### 4. Test Model Training

```python
from etl.supabase_client import SupabaseDB
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit

# Load data
db = SupabaseDB(url=SUPABASE_URL, key=SUPABASE_KEY)
df = db.query_to_dataframe("""
    select * from public.v_regression_dataset_optimized
    where symbol = 'SPY' and date >= '2010-01-01'
    order by date
""")

# Quick smoke test
feature_cols = [c for c in df.columns 
                if c not in ['symbol', 'date', 'primary_target']]
X, y = df[feature_cols].fillna(0), df['primary_target']

model = Ridge(alpha=1.0)
tscv = TimeSeriesSplit(n_splits=3)

for train_idx, test_idx in tscv.split(X):
    model.fit(X.iloc[train_idx], y.iloc[train_idx])
    r2 = model.score(X.iloc[test_idx], y.iloc[test_idx])
    print(f"R² = {r2:.4f}")
```

**Expected:** R² > 0 (positive predictive power)

---

## 🔍 TROUBLESHOOTING

### Issue: Migration fails with "column already exists"

**Cause:** Migration 007 already ran partially

**Fix:**
```sql
-- Check which columns exist
select column_name from information_schema.columns
where table_name = 'labels_daily'
  and column_name in ('primary_target', 'y_1d_vol_clip', 'y_5d_vol_clip');

-- If columns exist, migration already ran (OK to skip)
```

### Issue: Backfill fails with "column not found"

**Cause:** Migration didn't complete successfully

**Fix:**
1. Check migration output for errors
2. Rerun migration
3. Retry backfill

### Issue: Validation shows NaN in primary_target

**Cause:** Backfill didn't complete or failed for some symbols

**Fix:**
```bash
# Rerun backfill for specific symbol
python -m etl.main --symbols SPY --start 2000-01-01 --end 2025-12-13 --mode backfill
```

### Issue: Feature count mismatch (not 83)

**Cause:** JSON feature storage may have extra/missing keys

**Fix:**
- Check feature_json structure in database
- Verify feature computation logic matches expected
- This is a warning, not critical (SQL view extracts specific features)

### Issue: overnight_share not in [-1, 1]

**Cause:** Old formula still in code, or backfill didn't run

**Fix:**
1. Verify `etl/transform_features.py` has updated formula
2. Rerun backfill
3. Check database values

---

## 📊 ROLLBACK (If Needed)

If you need to rollback the changes:

```sql
begin;

-- Drop new views
drop view if exists public.v_regression_dataset_optimized cascade;
drop view if exists public.v_regression_diagnostics cascade;
drop view if exists public.v_feature_manifest cascade;
drop view if exists public.v_optimization_summary cascade;

-- Drop new tables
drop table if exists public.feature_exclusions cascade;

-- Remove new columns (optional - keeps old data intact)
alter table public.labels_daily
  drop column if exists primary_target,
  drop column if exists y_1d_vol_clip,
  drop column if exists y_5d_vol_clip;

-- Drop new metadata columns (optional)
alter table public.feature_metadata
  drop column if exists clip_min,
  drop column if exists clip_max,
  drop column if exists scaling_method,
  drop column if exists is_binary,
  drop column if exists is_excluded;

commit;
```

**Note:** This doesn't rollback data changes (recalculated features). To fully revert, restore from backup.

---

## 📚 NEXT STEPS AFTER DEPLOYMENT

1. **Train Baseline Models**
   ```bash
   # Coming soon: model training scripts
   ```

2. **Set Up Monitoring**
   - Track primary_target distribution over time
   - Monitor feature drift
   - Validate predictions vs actuals

3. **Experiment with Alternatives**
   - Try `y_5d_vol_clip` for longer horizons
   - Test ensemble methods
   - Add feature selection (LASSO, RFE)

4. **Production Pipeline**
   - Automate daily data updates
   - Add prediction serving
   - Implement walk-forward retraining

---

## 📖 DOCUMENTATION

**Quick Start:**
- `OPTIMIZATION_QUICK_REF.md` - Cheat sheet

**Full Details:**
- `OPTIMIZATION_SUMMARY.md` - Complete explanation
- `DATASET_OPTIMIZATION_CHANGELOG.md` - All changes

**Reference:**
- `FEATURE_MANIFEST.md` - Feature definitions
- `validate_regression_dataset.py` - Validation logic
- `etl/transform_normalization.py` - Normalization utilities

---

## 🆘 SUPPORT

**Common Issues:**
- Check `validate_regression_dataset.py` output
- Review migration logs
- Query `v_feature_manifest` for feature status
- Run `validate_regression_dataset()` SQL function

**Questions:**
- See documentation files listed above
- Check code comments in `etl/transform_*.py`
- Review SQL migration comments

---

## ✅ DEPLOYMENT COMPLETE

After successful deployment, you should have:

✅ Primary target (`primary_target`) designated and populated  
✅ Stable `overnight_share` formula applied  
✅ 12 redundant features documented as excluded  
✅ 83 optimized features available  
✅ Outlier clipping rules applied  
✅ Optimized views created (`v_regression_dataset_optimized`)  
✅ Validation framework operational  
✅ Documentation complete  

**Status:** Ready for production modeling

---

**Version:** 2.0 (Optimized)  
**Last Updated:** December 13, 2025
