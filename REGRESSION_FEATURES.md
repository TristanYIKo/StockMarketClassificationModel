# New Regression Features Quick Reference

## Total: 83 features (60 original + 23 new)

---

## NEW FEATURES (23)

### Overnight/Intraday (7)
```python
overnight_return       # log(today_open / yesterday_close)
intraday_return        # log(today_close / today_open)
overnight_mean_20      # 20-day mean of overnight returns
overnight_std_20       # 20-day std of overnight returns
intraday_mean_20       # 20-day mean of intraday returns
intraday_std_20        # 20-day std of intraday returns
overnight_share        # overnight_return / total_daily_return
```

### Trend Quality (3)
```python
adx_14                 # Average Directional Index (>25 = strong trend)
return_autocorr_20     # 20-day return autocorrelation (lag 1)
price_rsq_20           # R² of price vs time (linear trend fit)
```

### Lagged Features (9)
```python
log_ret_1d_lag1        # Yesterday's 1d return
log_ret_1d_lag2        # 2 days ago 1d return
log_ret_1d_lag3        # 3 days ago 1d return
log_ret_1d_lag5        # 5 days ago 1d return
vix_change_lag1        # Yesterday's VIX 1d change
vix_change_lag3        # 3 days ago VIX 1d change
hy_oas_change_lag1     # Yesterday's HY OAS 1d change
yield_curve_slope_lag1 # Yesterday's yield curve slope
```

### Regime Flags (4)
```python
high_vol_regime               # 1 if VIX > 20 OR VIX > 75th percentile
curve_inverted                # 1 if DGS10 < DGS2
credit_stress                 # 1 if HY OAS > 80th percentile
liquidity_expanding_regime    # 1 if Fed balance sheet 4-week change > 0
```

---

## NEW TARGETS (6)

### Regression Targets (PRIMARY)
```python
y_1d_raw        # 1-day forward log return (unscaled)
y_5d_raw        # 5-day forward log return (unscaled)
y_1d_vol        # 1-day return / rolling_vol_20 ← USE THIS
y_5d_vol        # 5-day return / rolling_vol_20 ← USE THIS
y_1d_clipped    # 1-day return clipped to ±3σ
y_5d_clipped    # 5-day return clipped to ±3σ
```

### Classification Targets (LEGACY)
```python
y_1d            # Binary: 1 if next day up
y_5d            # Binary: 1 if 5 days ahead up
y_thresh        # Binary: 1 if next day > threshold
```

---

## ORIGINAL FEATURES (60)

### Technical (22)
```python
log_ret_1d, log_ret_5d, log_ret_20d, rsi_14, macd_hist,
vol_5, vol_20, vol_60, atr_14, high_low_pct, close_open_pct,
sma_20, sma_50, sma_200, ema_20, ema_50, sma20_gt_sma50,
volume_z, volume_chg_pct, dd_60, dow, days_since_prev
```

### Macro (12)
```python
dgs2, dgs10, yield_curve_slope, dgs10_change_1d, dgs10_change_5d,
hy_oas_level, hy_oas_change_1d, hy_oas_change_5d,
liquidity_expanding, fed_bs_chg_pct, rrp_level, rrp_chg_pct_5d
```

### VIX (4)
```python
vix_level, vix_change_1d, vix_change_5d, vix_term_structure
```

### Cross-Asset (8)
```python
dxy_ret_5d, gold_ret_5d, oil_ret_5d,
hyg_ret_5d, hyg_vs_spy_5d, hyg_spy_corr_20d,
lqd_ret_5d, tlt_ret_5d
```

### Breadth (4)
```python
rsp_spy_ratio, rsp_spy_ratio_z, qqq_spy_ratio_z, iwm_spy_ratio_z
```

### Events (3)
```python
is_fomc, is_cpi_release, is_nfp_release
```

### OHLCV (6)
```python
open, high, low, close, adj_close, volume
```

### Metadata (1)
```python
symbol
```

---

## Python Feature List (Copy-Paste)

```python
REGRESSION_FEATURES = [
    # Technical (22)
    'log_ret_1d', 'log_ret_5d', 'log_ret_20d', 'rsi_14', 'macd_hist',
    'vol_5', 'vol_20', 'vol_60', 'atr_14', 'high_low_pct', 'close_open_pct',
    'sma_20', 'sma_50', 'sma_200', 'ema_20', 'ema_50', 'sma20_gt_sma50',
    'volume_z', 'volume_chg_pct', 'dd_60', 'dow', 'days_since_prev',
    
    # Overnight/Intraday (7) - NEW
    'overnight_return', 'intraday_return',
    'overnight_mean_20', 'overnight_std_20',
    'intraday_mean_20', 'intraday_std_20', 'overnight_share',
    
    # Trend Quality (3) - NEW
    'adx_14', 'return_autocorr_20', 'price_rsq_20',
    
    # Macro (12)
    'dgs2', 'dgs10', 'yield_curve_slope', 'dgs10_change_1d', 'dgs10_change_5d',
    'hy_oas_level', 'hy_oas_change_1d', 'hy_oas_change_5d',
    'liquidity_expanding', 'fed_bs_chg_pct', 'rrp_level', 'rrp_chg_pct_5d',
    
    # VIX (4)
    'vix_level', 'vix_change_1d', 'vix_change_5d', 'vix_term_structure',
    
    # Cross-asset (8)
    'dxy_ret_5d', 'gold_ret_5d', 'oil_ret_5d',
    'hyg_ret_5d', 'hyg_vs_spy_5d', 'hyg_spy_corr_20d',
    'lqd_ret_5d', 'tlt_ret_5d',
    
    # Breadth (4)
    'rsp_spy_ratio', 'rsp_spy_ratio_z', 'qqq_spy_ratio_z', 'iwm_spy_ratio_z',
    
    # Lagged (9) - NEW
    'log_ret_1d_lag1', 'log_ret_1d_lag2', 'log_ret_1d_lag3', 'log_ret_1d_lag5',
    'vix_change_lag1', 'vix_change_lag3',
    'hy_oas_change_lag1', 'yield_curve_slope_lag1',
    
    # Regimes (4) - NEW
    'high_vol_regime', 'curve_inverted', 'credit_stress', 'liquidity_expanding_regime',
    
    # Events (3)
    'is_fomc', 'is_cpi_release', 'is_nfp_release',
]

# 83 features total
assert len(REGRESSION_FEATURES) == 83

# Use this target
REGRESSION_TARGET = 'y_1d_vol'
```

---

## SQL Select Statement (Copy-Paste)

```sql
SELECT 
  symbol, date,
  
  -- OHLCV
  open, high, low, close, adj_close, volume,
  
  -- Technical (22)
  log_ret_1d, log_ret_5d, log_ret_20d, rsi_14, macd_hist,
  vol_5, vol_20, vol_60, atr_14, high_low_pct, close_open_pct,
  sma_20, sma_50, sma_200, ema_20, ema_50, sma20_gt_sma50,
  volume_z, volume_chg_pct, dd_60, dow, days_since_prev,
  
  -- Overnight/Intraday (7) NEW
  overnight_return, intraday_return,
  overnight_mean_20, overnight_std_20,
  intraday_mean_20, intraday_std_20, overnight_share,
  
  -- Trend Quality (3) NEW
  adx_14, return_autocorr_20, price_rsq_20,
  
  -- Macro (12)
  dgs2, dgs10, yield_curve_slope, dgs10_change_1d, dgs10_change_5d,
  hy_oas_level, hy_oas_change_1d, hy_oas_change_5d,
  liquidity_expanding, fed_bs_chg_pct, rrp_level, rrp_chg_pct_5d,
  
  -- VIX (4)
  vix_level, vix_change_1d, vix_change_5d, vix_term_structure,
  
  -- Cross-asset (8)
  dxy_ret_5d, gold_ret_5d, oil_ret_5d,
  hyg_ret_5d, hyg_vs_spy_5d, hyg_spy_corr_20d,
  lqd_ret_5d, tlt_ret_5d,
  
  -- Breadth (4)
  rsp_spy_ratio, rsp_spy_ratio_z, qqq_spy_ratio_z, iwm_spy_ratio_z,
  
  -- Lagged (9) NEW
  log_ret_1d_lag1, log_ret_1d_lag2, log_ret_1d_lag3, log_ret_1d_lag5,
  vix_change_lag1, vix_change_lag3,
  hy_oas_change_lag1, yield_curve_slope_lag1,
  
  -- Regimes (4) NEW
  high_vol_regime, curve_inverted, credit_stress, liquidity_expanding_regime,
  
  -- Events (3)
  is_fomc, is_cpi_release, is_nfp_release,
  
  -- Regression Targets (PRIMARY)
  y_1d_vol, y_5d_vol,
  y_1d_raw, y_5d_raw,
  y_1d_clipped, y_5d_clipped,
  
  -- Classification Targets (LEGACY)
  y_1d_class, y_5d_class, y_thresh_class
  
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND date >= '2001-01-01'  -- After 265-day warm-up
ORDER BY date;
```

---

## Feature Importance Expected (Top 20)

Based on quantitative research, expect these to rank highest:

1. **log_ret_1d_lag1** - Yesterday's return (mean reversion/momentum)
2. **vol_20** - Current volatility regime
3. **high_vol_regime** - Binary volatility state
4. **overnight_return** - Gap risk premium
5. **vix_change_1d** - Volatility shock
6. **log_ret_1d_lag2** - 2-day return memory
7. **adx_14** - Trend strength
8. **return_autocorr_20** - Momentum/reversion regime
9. **yield_curve_slope** - Macro regime
10. **rsi_14** - Overbought/oversold
11. **curve_inverted** - Recession signal
12. **overnight_share** - Risk partition
13. **vix_change_lag1** - Lagged volatility shock
14. **hy_oas_level** - Credit stress level
15. **intraday_return** - Session return
16. **log_ret_5d** - Weekly momentum
17. **credit_stress** - Binary credit regime
18. **macd_hist** - Momentum divergence
19. **dow** - Day of week effect
20. **hyg_spy_corr_20d** - Risk-on/risk-off

---

## Warm-up Period

**Minimum:** 265 days

**Breakdown:**
- 200 days for SMA200
- 60 days for vol_60, rolling percentiles
- 5 days for lag5

**Recommended Training Start:** 2001-01-01 (assuming data from 2000-01-01)

---

## Storage

**Database:**
- Features stored in `features_daily.feature_json` (JSONB)
- Labels stored in `labels_daily` (explicit columns)
- View: `v_regression_dataset` (exploded features + targets)

**File Export:**
```python
df.to_parquet('spy_regression_data.parquet')  # Efficient storage
df.to_csv('spy_regression_data.csv')          # Human-readable
```

---

## See Also

- **REGRESSION_UPGRADE.md** - Complete guide
- **REGRESSION_SUMMARY.md** - Implementation summary
- **example_queries_regression.sql** - SQL examples
- **migrations/005_regression_features.sql** - Schema changes
