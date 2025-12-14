-- Example Queries for Regression Dataset

-- =========================================
-- 1. BASIC QUERIES
-- =========================================

-- Get full regression dataset for SPY
SELECT *
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND date >= '2023-01-01'
ORDER BY date;

-- Get only key regression features
SELECT 
  symbol, date, close,
  -- Volatility-scaled targets
  y_1d_vol, y_5d_vol,
  -- Overnight/intraday
  overnight_return, intraday_return, overnight_share,
  -- Trend quality
  adx_14, return_autocorr_20, price_rsq_20,
  -- Lagged returns
  log_ret_1d_lag1, log_ret_1d_lag2, log_ret_1d_lag3,
  -- Regime flags
  high_vol_regime, curve_inverted, credit_stress
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND date >= '2024-01-01'
ORDER BY date;

-- =========================================
-- 2. REGIME ANALYSIS
-- =========================================

-- Count days in each regime
SELECT 
  symbol,
  SUM(high_vol_regime) as high_vol_days,
  SUM(curve_inverted) as inverted_days,
  SUM(credit_stress) as credit_stress_days,
  SUM(liquidity_expanding_regime) as liquidity_expanding_days,
  COUNT(*) as total_days
FROM v_regression_dataset
WHERE symbol = 'SPY'
GROUP BY symbol;

-- Find days with multiple regimes active
SELECT 
  date, vix_level, dgs10, dgs2, hy_oas_level,
  high_vol_regime, curve_inverted, credit_stress
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND (high_vol_regime + curve_inverted + credit_stress) >= 2
ORDER BY date DESC;

-- Analyze returns by regime
SELECT 
  high_vol_regime,
  COUNT(*) as days,
  AVG(y_1d_raw) as mean_return,
  STDDEV(y_1d_raw) as std_return,
  AVG(ABS(y_1d_raw)) as mean_abs_return
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND y_1d_raw IS NOT NULL
GROUP BY high_vol_regime;

-- =========================================
-- 3. OVERNIGHT VS INTRADAY ANALYSIS
-- =========================================

-- Compare overnight vs intraday returns
SELECT 
  symbol,
  AVG(overnight_return) as avg_overnight,
  AVG(intraday_return) as avg_intraday,
  STDDEV(overnight_return) as std_overnight,
  STDDEV(intraday_return) as std_intraday,
  CORR(overnight_return, intraday_return) as correlation
FROM v_regression_dataset
WHERE symbol IN ('SPY', 'QQQ', 'DIA', 'IWM')
  AND overnight_return IS NOT NULL
GROUP BY symbol;

-- Find days with large overnight gaps
SELECT 
  date, close, overnight_return, intraday_return,
  overnight_return + intraday_return as total_return,
  high_vol_regime, is_fomc, is_cpi_release, is_nfp_release
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND ABS(overnight_return) > 0.015  -- >1.5% overnight gap
ORDER BY ABS(overnight_return) DESC
LIMIT 50;

-- =========================================
-- 4. TREND QUALITY ANALYSIS
-- =========================================

-- Find strong trending periods (high ADX)
SELECT 
  date, close, adx_14, return_autocorr_20, price_rsq_20,
  log_ret_1d, log_ret_5d
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND adx_14 > 30  -- Strong trend
  AND date >= '2023-01-01'
ORDER BY adx_14 DESC
LIMIT 50;

-- Find choppy periods (low ADX, low R²)
SELECT 
  date, close, adx_14, return_autocorr_20, price_rsq_20,
  vol_20, high_vol_regime
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND adx_14 < 15  -- Weak trend
  AND price_rsq_20 < 0.3  -- Low linear fit
  AND date >= '2023-01-01'
ORDER BY date DESC
LIMIT 50;

-- =========================================
-- 5. LAG VALIDATION (NO LEAKAGE CHECKS)
-- =========================================

-- Verify lag1 matches previous day's value
WITH data AS (
  SELECT 
    date,
    log_ret_1d,
    log_ret_1d_lag1,
    LAG(log_ret_1d, 1) OVER (ORDER BY date) as prev_log_ret_1d
  FROM v_regression_dataset
  WHERE symbol = 'SPY'
    AND date >= '2024-01-01'
  ORDER BY date
)
SELECT 
  date,
  log_ret_1d,
  log_ret_1d_lag1,
  prev_log_ret_1d,
  CASE 
    WHEN log_ret_1d_lag1 IS NULL THEN 'First row (expected NULL)'
    WHEN ABS(log_ret_1d_lag1 - prev_log_ret_1d) < 0.0001 THEN '✓ OK'
    ELSE '✗ MISMATCH'
  END as validation
FROM data
LIMIT 20;

-- Check lag pattern for all lagged features
SELECT 
  date,
  log_ret_1d_lag1 IS NOT NULL as has_lag1,
  log_ret_1d_lag2 IS NOT NULL as has_lag2,
  log_ret_1d_lag3 IS NOT NULL as has_lag3,
  log_ret_1d_lag5 IS NOT NULL as has_lag5,
  vix_change_lag1 IS NOT NULL as has_vix_lag1
FROM v_regression_dataset
WHERE symbol = 'SPY'
ORDER BY date
LIMIT 10;

-- =========================================
-- 6. TARGET QUALITY CHECKS
-- =========================================

-- Compare raw vs vol-scaled target distributions
SELECT 
  symbol,
  AVG(y_1d_raw) as mean_raw,
  STDDEV(y_1d_raw) as std_raw,
  AVG(y_1d_vol) as mean_vol_scaled,
  STDDEV(y_1d_vol) as std_vol_scaled,
  STDDEV(y_1d_raw) / NULLIF(STDDEV(y_1d_vol), 0) as variance_ratio
FROM v_regression_dataset
WHERE symbol IN ('SPY', 'QQQ', 'DIA', 'IWM')
  AND y_1d_raw IS NOT NULL
GROUP BY symbol;

-- Check for outliers in targets
SELECT 
  date, close, vol_20,
  y_1d_raw, y_1d_vol, y_1d_clipped,
  y_1d_raw / NULLIF(vol_20, 0) as manual_scaled,
  high_vol_regime
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND ABS(y_1d_raw) > 0.03  -- Large raw return
ORDER BY ABS(y_1d_raw) DESC
LIMIT 20;

-- =========================================
-- 7. FEATURE COMPLETENESS
-- =========================================

-- Count non-null values for key features
SELECT 
  symbol,
  COUNT(*) as total_rows,
  COUNT(y_1d_vol) as has_target,
  COUNT(adx_14) as has_adx,
  COUNT(overnight_return) as has_overnight,
  COUNT(log_ret_1d_lag1) as has_lag1,
  COUNT(high_vol_regime) as has_regime,
  100.0 * COUNT(y_1d_vol) / NULLIF(COUNT(*), 0) as target_pct
FROM v_regression_dataset
WHERE symbol IN ('SPY', 'QQQ', 'DIA', 'IWM')
GROUP BY symbol;

-- Find rows with many NaN features
SELECT 
  date, symbol,
  CASE WHEN y_1d_vol IS NULL THEN 1 ELSE 0 END +
  CASE WHEN adx_14 IS NULL THEN 1 ELSE 0 END +
  CASE WHEN overnight_return IS NULL THEN 1 ELSE 0 END +
  CASE WHEN log_ret_1d_lag1 IS NULL THEN 1 ELSE 0 END +
  CASE WHEN vix_level IS NULL THEN 1 ELSE 0 END +
  CASE WHEN dgs10 IS NULL THEN 1 ELSE 0 END as nan_count
FROM v_regression_dataset
WHERE symbol = 'SPY'
ORDER BY nan_count DESC, date DESC
LIMIT 50;

-- =========================================
-- 8. TIME-SERIES SPLIT HELPERS
-- =========================================

-- Get date ranges for train/val/test splits
WITH date_stats AS (
  SELECT 
    symbol,
    MIN(date) as min_date,
    MAX(date) as max_date,
    COUNT(*) as total_rows,
    PERCENTILE_CONT(0.70) WITHIN GROUP (ORDER BY date) as train_end,
    PERCENTILE_CONT(0.85) WITHIN GROUP (ORDER BY date) as val_end
  FROM v_regression_dataset
  WHERE symbol = 'SPY'
    AND y_1d_vol IS NOT NULL
  GROUP BY symbol
)
SELECT 
  symbol,
  min_date,
  train_end,
  val_end,
  max_date,
  total_rows,
  ROUND(0.70 * total_rows) as train_rows,
  ROUND(0.15 * total_rows) as val_rows,
  ROUND(0.15 * total_rows) as test_rows
FROM date_stats;

-- =========================================
-- 9. FEATURE IMPORTANCE DATA PREP
-- =========================================

-- Export data for modeling (training set only)
SELECT 
  date, symbol,
  -- All features go here
  log_ret_1d, log_ret_5d, log_ret_20d, rsi_14, macd_hist,
  vol_5, vol_20, vol_60, atr_14, high_low_pct, close_open_pct,
  sma_20, sma_50, sma_200, ema_20, ema_50, sma20_gt_sma50,
  volume_z, volume_chg_pct, dd_60, dow, days_since_prev,
  overnight_return, intraday_return, overnight_mean_20, overnight_std_20,
  intraday_mean_20, intraday_std_20, overnight_share,
  adx_14, return_autocorr_20, price_rsq_20,
  dgs2, dgs10, yield_curve_slope, dgs10_change_1d, dgs10_change_5d,
  hy_oas_level, hy_oas_change_1d, hy_oas_change_5d,
  liquidity_expanding, fed_bs_chg_pct, rrp_level, rrp_chg_pct_5d,
  vix_level, vix_change_1d, vix_change_5d, vix_term_structure,
  dxy_ret_5d, gold_ret_5d, oil_ret_5d, hyg_ret_5d, hyg_vs_spy_5d,
  hyg_spy_corr_20d, lqd_ret_5d, tlt_ret_5d,
  rsp_spy_ratio, rsp_spy_ratio_z, qqq_spy_ratio_z, iwm_spy_ratio_z,
  log_ret_1d_lag1, log_ret_1d_lag2, log_ret_1d_lag3, log_ret_1d_lag5,
  vix_change_lag1, vix_change_lag3, hy_oas_change_lag1, yield_curve_slope_lag1,
  high_vol_regime, curve_inverted, credit_stress, liquidity_expanding_regime,
  is_fomc, is_cpi_release, is_nfp_release,
  -- Target
  y_1d_vol
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND date >= '2001-01-01'  -- After 260-day warm-up from 2000-01-01
  AND date < '2023-01-01'   -- Training set
  AND y_1d_vol IS NOT NULL
ORDER BY date;

-- =========================================
-- 10. CORRELATION ANALYSIS
-- =========================================

-- Check correlation between lagged returns and forward returns
SELECT 
  CORR(log_ret_1d_lag1, y_1d_raw) as lag1_corr,
  CORR(log_ret_1d_lag2, y_1d_raw) as lag2_corr,
  CORR(log_ret_1d_lag3, y_1d_raw) as lag3_corr,
  CORR(log_ret_1d_lag5, y_1d_raw) as lag5_corr
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND y_1d_raw IS NOT NULL;
-- Negative = mean reversion, Positive = momentum

-- Check regime impact on returns
SELECT 
  high_vol_regime,
  curve_inverted,
  credit_stress,
  COUNT(*) as days,
  AVG(y_1d_vol) as avg_vol_scaled_return,
  STDDEV(y_1d_vol) as std_vol_scaled_return
FROM v_regression_dataset
WHERE symbol = 'SPY'
  AND y_1d_vol IS NOT NULL
GROUP BY high_vol_regime, curve_inverted, credit_stress
ORDER BY high_vol_regime, curve_inverted, credit_stress;
