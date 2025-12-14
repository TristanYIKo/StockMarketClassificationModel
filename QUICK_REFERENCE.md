# Quick Reference: Classification Model

## 83 Total Features for y_class_1d Prediction

**Target:** `y_class_1d` → -1 (Sell), 0 (Hold), 1 (Buy)  
**Threshold:** ±0.25 volatility-scaled returns  
**Dataset:** `v_classification_dataset_1d` (25,907 rows)

### Technical (22)
```
log_ret_1d, log_ret_5d, log_ret_20d, rsi_14, macd_hist,
vol_5, vol_20, vol_60, atr_14, high_low_pct, close_open_pct,
sma_20, sma_50, sma_200, ema_20, ema_50, sma20_gt_sma50,
volume_z, volume_chg_pct, dd_60, dow, days_since_prev
```

### Macro (12)
```
dgs2, dgs10, yield_curve_slope, dgs10_change_1d, dgs10_change_5d,
hy_oas_level, hy_oas_change_1d, hy_oas_change_5d,
liquidity_expanding, fed_bs_chg_pct, rrp_level, rrp_chg_pct_5d
```

### VIX (4)
```
vix_level, vix_change_1d, vix_change_5d, vix_term_structure
```

### Cross-Asset (8)
```
dxy_ret_5d, gold_ret_5d, oil_ret_5d,
hyg_ret_5d, hyg_vs_spy_5d, hyg_spy_corr_20d,
lqd_ret_5d, tlt_ret_5d
```

### Breadth (4)
```
rsp_spy_ratio, rsp_spy_ratio_z, qqq_spy_ratio_z, iwm_spy_ratio_z
```

### Events (3)
```
is_fomc, is_cpi_release, is_nfp_release
```

### OHLCV (6)
```
open, high, low, close, adj_close, volume
```

### Metadata (1)
```
symbol
```

---

## Dropped Features

```
SMA 5/10, EMA 5/10/200, MACD line/signal,
log_ret_10d, vol_10d, OBV, dd_20, month,
is_month_end, is_quarter_end, is_options_expiry_week
```

---

## Key SQL Queries

### Get full dataset
```sql
select * from v_model_dataset
where symbol = 'SPY' and date >= '2021-01-01'
order by date;
```

### Check event calendar
```sql
select event_type, count(*) as count
from events_calendar
group by event_type;
-- Expected: fomc (~8), cpi_release (~12), nfp_release (~12)
```

### Verify feature columns
```sql
select * from v_features_pruned
where asset_id = (select id from assets where symbol = 'SPY')
limit 5;
-- Should have 53 feature columns + date, asset_id, id, created_at
```

---

## Python Usage

```python
from etl.supabase_client import SupabaseDB
import pandas as pd

db = SupabaseDB()

# Get pruned dataset for SPY
result = db.client.table('v_model_dataset').select('*').eq('symbol', 'SPY').execute()
df = pd.DataFrame(result.data)

# Feature names
FEATURE_COLS = [
    # Technical
    'log_ret_1d', 'log_ret_5d', 'log_ret_20d', 'rsi_14', 'macd_hist',
    'vol_5', 'vol_20', 'vol_60', 'atr_14', 'high_low_pct', 'close_open_pct',
    'sma_20', 'sma_50', 'sma_200', 'ema_20', 'ema_50', 'sma20_gt_sma50',
    'volume_z', 'volume_chg_pct', 'dd_60', 'dow', 'days_since_prev',
    
    # Macro
    'dgs2', 'dgs10', 'yield_curve_slope', 'dgs10_change_1d', 'dgs10_change_5d',
    'hy_oas_level', 'hy_oas_change_1d', 'hy_oas_change_5d',
    'liquidity_expanding', 'fed_bs_chg_pct', 'rrp_level', 'rrp_chg_pct_5d',
    
    # VIX
    'vix_level', 'vix_change_1d', 'vix_change_5d', 'vix_term_structure',
    
    # Cross-asset
    'dxy_ret_5d', 'gold_ret_5d', 'oil_ret_5d',
    'hyg_ret_5d', 'hyg_vs_spy_5d', 'hyg_spy_corr_20d',
    'lqd_ret_5d', 'tlt_ret_5d',
    
    # Breadth
    'rsp_spy_ratio', 'rsp_spy_ratio_z', 'qqq_spy_ratio_z', 'iwm_spy_ratio_z',
    
    # Events
    'is_fomc', 'is_cpi_release', 'is_nfp_release',
    
    # OHLCV
    'open', 'high', 'low', 'close', 'adj_close', 'volume'
]

LABEL_COLS = ['y_1d', 'y_5d', 'y_thresh']

# Split
X = df[FEATURE_COLS].iloc[260:]  # Skip 260-day warm-up
y = df['y_thresh'].iloc[260:]

# Model
from sklearn.ensemble import RandomForestClassifier
clf = RandomForestClassifier(n_estimators=100)
clf.fit(X, y)

# Feature importance
importances = pd.DataFrame({
    'feature': FEATURE_COLS,
    'importance': clf.feature_importances_
}).sort_values('importance', ascending=False)
print(importances.head(20))
```

---

## Training Checklist

- [ ] Load data from `v_model_dataset`
- [ ] Filter to symbol (SPY, QQQ, DIA, or IWM)
- [ ] Skip first 260 rows (warm-up period for SMA200)
- [ ] Split train/val/test by date (e.g., 2001-2022, 2023, 2024)
- [ ] Handle NaN (forward-fill or drop)
- [ ] Normalize features (StandardScaler or MinMaxScaler)
- [ ] Train model (RF, XGB, LGBM)
- [ ] Evaluate on OOS test set
- [ ] Check feature importance
- [ ] Validate no leakage (labels use future closes)

---

## Warm-up Period

**First 260 trading days (~1 year)** may have NaN due to:
- SMA200 needs 200 days
- vol_60 needs 60 days
- Rolling correlations need 20 days

**Solution:** Skip first 260 rows or forward-fill NaN conservatively.

---

## Event Calendar

**Only 3 event types (high-ROI macro releases):**

| Event | Frequency | Example Dates |
|-------|-----------|---------------|
| FOMC | ~8/year | Jan 31, Mar 20, May 1, Jun 12, Jul 31, Sep 18, Nov 7, Dec 18 |
| CPI | ~12/year | ~13th of each month |
| NFP | ~12/year | First Friday of each month |

**Total:** ~32 events/year (vs 250 before pruning)

---

## Data Quality

Run validation checks:
```powershell
python validate_data_quality.py
```

Expected output:
```
✓ No duplicates in features_daily
✓ All event types valid: {'fomc', 'cpi_release', 'nfp_release'}
✓ SPY: 260+ days warm-up (sufficient)
✓ NaN pattern looks reasonable (concentrated in warm-up period)
✓ Found overlapping dates for validation
✓ Feature count matches manifest
```

---

## Need Help?

See:
- [FEATURE_MANIFEST.md](FEATURE_MANIFEST.md) - Complete feature documentation
- [PRUNING_SUMMARY.md](PRUNING_SUMMARY.md) - Detailed pruning implementation
- [README.md](README.md) - Project overview and setup
