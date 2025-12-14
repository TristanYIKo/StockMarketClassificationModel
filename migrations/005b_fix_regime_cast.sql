-- Migration: Fix regime flag casting (int -> numeric -> int)
-- Fixes: ERROR: 22P02: invalid input syntax for type integer: "1.0"
-- Date: 2025-12-13

begin;

-- Drop and recreate view with correct casting
drop view if exists public.v_regression_dataset cascade;

create or replace view public.v_regression_dataset as
select 
  a.symbol,
  db.date,
  
  -- OHLCV
  db.open, 
  db.high, 
  db.low, 
  db.close, 
  db.adj_close, 
  db.volume,
  
  -- Technical features (from features_daily.feature_json)
  (fp.feature_json->>'log_ret_1d')::numeric as log_ret_1d,
  (fp.feature_json->>'log_ret_5d')::numeric as log_ret_5d,
  (fp.feature_json->>'log_ret_20d')::numeric as log_ret_20d,
  (fp.feature_json->>'rsi_14')::numeric as rsi_14,
  (fp.feature_json->>'macd_hist')::numeric as macd_hist,
  (fp.feature_json->>'vol_5')::numeric as vol_5,
  (fp.feature_json->>'vol_20')::numeric as vol_20,
  (fp.feature_json->>'vol_60')::numeric as vol_60,
  (fp.feature_json->>'atr_14')::numeric as atr_14,
  (fp.feature_json->>'high_low_pct')::numeric as high_low_pct,
  (fp.feature_json->>'close_open_pct')::numeric as close_open_pct,
  (fp.feature_json->>'sma_20')::numeric as sma_20,
  (fp.feature_json->>'sma_50')::numeric as sma_50,
  (fp.feature_json->>'ema_12')::numeric as ema_12,
  (fp.feature_json->>'ema_26')::numeric as ema_26,
  (fp.feature_json->>'bollinger_width')::numeric as bollinger_width,
  (fp.feature_json->>'upper_shadow')::numeric as upper_shadow,
  (fp.feature_json->>'lower_shadow')::numeric as lower_shadow,
  (fp.feature_json->>'body_size')::numeric as body_size,
  (fp.feature_json->>'volume_ratio_20d')::numeric as volume_ratio_20d,
  (fp.feature_json->>'volume_trend_20d')::numeric as volume_trend_20d,
  
  -- Overnight/intraday features (NEW)
  (fp.feature_json->>'overnight_return')::numeric as overnight_return,
  (fp.feature_json->>'intraday_return')::numeric as intraday_return,
  (fp.feature_json->>'overnight_mean_20')::numeric as overnight_mean_20,
  (fp.feature_json->>'overnight_std_20')::numeric as overnight_std_20,
  (fp.feature_json->>'intraday_mean_20')::numeric as intraday_mean_20,
  (fp.feature_json->>'intraday_std_20')::numeric as intraday_std_20,
  (fp.feature_json->>'overnight_share')::numeric as overnight_share,
  
  -- Trend quality features (NEW)
  (fp.feature_json->>'adx_14')::numeric as adx_14,
  (fp.feature_json->>'return_autocorr_20')::numeric as return_autocorr_20,
  (fp.feature_json->>'price_rsq_20')::numeric as price_rsq_20,
  
  -- Macro features
  (fp.feature_json->>'DGS2')::numeric as dgs2,
  (fp.feature_json->>'DGS10')::numeric as dgs10,
  (fp.feature_json->>'yield_curve_slope')::numeric as yield_curve_slope,
  (fp.feature_json->>'effr_level')::numeric as effr_level,
  (fp.feature_json->>'sofr_level')::numeric as sofr_level,
  (fp.feature_json->>'real_rate_proxy')::numeric as real_rate_proxy,
  (fp.feature_json->>'hy_oas_level')::numeric as hy_oas_level,
  (fp.feature_json->>'hy_oas_change')::numeric as hy_oas_change,
  (fp.feature_json->>'hy_oas_z')::numeric as hy_oas_z,
  (fp.feature_json->>'fed_balance_sheet_change_pct')::numeric as fed_balance_sheet_change_pct,
  (fp.feature_json->>'rrp_change_pct_5d')::numeric as rrp_change_pct_5d,
  
  -- Volatility features
  (fp.feature_json->>'vix_level')::numeric as vix_level,
  (fp.feature_json->>'vix_change')::numeric as vix_change,
  (fp.feature_json->>'vix_z')::numeric as vix_z,
  (fp.feature_json->>'vix9d_level')::numeric as vix9d_level,
  (fp.feature_json->>'vix_term_structure')::numeric as vix_term_structure,
  (fp.feature_json->>'vvix_level')::numeric as vvix_level,
  
  -- Currency and commodity proxies
  (fp.feature_json->>'usd_strength')::numeric as usd_strength,
  (fp.feature_json->>'gold_ret_5d')::numeric as gold_ret_5d,
  (fp.feature_json->>'oil_ret_5d')::numeric as oil_ret_5d,
  
  -- Credit proxies
  (fp.feature_json->>'hyg_ret_5d')::numeric as hyg_ret_5d,
  (fp.feature_json->>'hyg_vs_spy_5d')::numeric as hyg_vs_spy_5d,
  (fp.feature_json->>'hyg_spy_corr_20d')::numeric as hyg_spy_corr_20d,
  (fp.feature_json->>'lqd_ret_5d')::numeric as lqd_ret_5d,
  (fp.feature_json->>'tlt_ret_5d')::numeric as tlt_ret_5d,
  
  -- Breadth features
  (fp.feature_json->>'rsp_spy_ratio')::numeric as rsp_spy_ratio,
  (fp.feature_json->>'rsp_spy_ratio_z')::numeric as rsp_spy_ratio_z,
  (fp.feature_json->>'qqq_spy_ratio_z')::numeric as qqq_spy_ratio_z,
  (fp.feature_json->>'iwm_spy_ratio_z')::numeric as iwm_spy_ratio_z,
  
  -- Lagged features (NEW)
  (fp.feature_json->>'log_ret_1d_lag1')::numeric as log_ret_1d_lag1,
  (fp.feature_json->>'log_ret_1d_lag2')::numeric as log_ret_1d_lag2,
  (fp.feature_json->>'log_ret_1d_lag3')::numeric as log_ret_1d_lag3,
  (fp.feature_json->>'log_ret_1d_lag5')::numeric as log_ret_1d_lag5,
  (fp.feature_json->>'vix_change_lag1')::numeric as vix_change_lag1,
  (fp.feature_json->>'vix_change_lag3')::numeric as vix_change_lag3,
  (fp.feature_json->>'hy_oas_change_lag1')::numeric as hy_oas_change_lag1,
  (fp.feature_json->>'yield_curve_slope_lag1')::numeric as yield_curve_slope_lag1,
  
  -- Regime flags (NEW) - FIXED: numeric -> int to handle "1.0" strings
  ((fp.feature_json->>'high_vol_regime')::numeric)::int as high_vol_regime,
  ((fp.feature_json->>'curve_inverted')::numeric)::int as curve_inverted,
  ((fp.feature_json->>'credit_stress')::numeric)::int as credit_stress,
  ((fp.feature_json->>'liquidity_expanding_regime')::numeric)::int as liquidity_expanding_regime,
  
  -- Event flags
  ((fp.feature_json->>'is_fomc')::numeric)::int as is_fomc,
  ((fp.feature_json->>'is_cpi_release')::numeric)::int as is_cpi_release,
  ((fp.feature_json->>'is_nfp_release')::numeric)::int as is_nfp_release,
  
  -- REGRESSION TARGETS (volatility-scaled)
  l.y_1d_raw,
  l.y_5d_raw,
  l.y_1d_vol,
  l.y_5d_vol,
  l.y_1d_clipped,
  l.y_5d_clipped,
  
  -- Classification targets (legacy)
  l.y_1d as y_1d_class, 
  l.y_5d as y_5d_class, 
  l.y_thresh as y_thresh_class
  
from public.daily_bars db
join public.assets a on a.id = db.asset_id
left join public.features_daily fp on fp.asset_id = db.asset_id and fp.date = db.date
left join public.labels_daily l on l.asset_id = db.asset_id and l.date = db.date
where a.asset_type = 'ETF';

comment on view public.v_regression_dataset is 
  'Regression modeling dataset with volatility-scaled targets, lagged features, and regime flags';

commit;
