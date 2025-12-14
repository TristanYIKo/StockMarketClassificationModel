-- Migration: Fix integer casting for v_features_pruned and v_model_dataset
-- Fixes: ERROR: 22P02: invalid input syntax for type integer: "1.0"
-- Date: 2025-12-13

begin;

-- =========================================
-- FIX v_features_pruned VIEW
-- =========================================

create or replace view public.v_features_pruned as
select 
  id,
  asset_id,
  date,
  
  -- Returns / momentum (keep 1d, 5d, 20d; drop 10d)
  (feature_json->>'log_ret_1d')::numeric as log_ret_1d,
  (feature_json->>'log_ret_5d')::numeric as log_ret_5d,
  (feature_json->>'log_ret_20d')::numeric as log_ret_20d,
  (feature_json->>'rsi_14')::numeric as rsi_14,
  
  -- MACD (keep histogram only; drop line and signal)
  (feature_json->>'macd_hist')::numeric as macd_hist,
  
  -- Volatility / range (keep 5d, 20d, 60d; drop 10d)
  (feature_json->>'vol_5')::numeric as vol_5,
  (feature_json->>'vol_20')::numeric as vol_20,
  (feature_json->>'vol_60')::numeric as vol_60,
  (feature_json->>'atr_14')::numeric as atr_14,
  (feature_json->>'high_low_pct')::numeric as high_low_pct,
  (feature_json->>'close_open_pct')::numeric as close_open_pct,
  
  -- Moving averages (keep SMA 20/50/200, EMA 20/50; drop 5/10)
  (feature_json->>'sma_20')::numeric as sma_20,
  (feature_json->>'sma_50')::numeric as sma_50,
  (feature_json->>'sma_200')::numeric as sma_200,
  (feature_json->>'ema_20')::numeric as ema_20,
  (feature_json->>'ema_50')::numeric as ema_50,
  ((feature_json->>'sma20_gt_sma50')::numeric)::int as sma20_gt_sma50,
  
  -- Volume (keep zscore and change; drop OBV)
  (feature_json->>'volume_z')::numeric as volume_z,
  (feature_json->>'volume_chg_pct')::numeric as volume_chg_pct,
  
  -- Drawdown (keep 60d only; drop 20d)
  (feature_json->>'dd_60')::numeric as dd_60,
  
  -- Calendar (keep day_of_week and days_since_prev; drop month)
  ((feature_json->>'dow')::numeric)::int as dow,
  ((feature_json->>'days_since_prev')::numeric)::int as days_since_prev,
  
  -- Macro features (kept as-is from context merge)
  (feature_json->>'DGS2')::numeric as dgs2,
  (feature_json->>'DGS10')::numeric as dgs10,
  (feature_json->>'yield_curve_slope')::numeric as yield_curve_slope,
  (feature_json->>'dgs10_change_1d')::numeric as dgs10_change_1d,
  (feature_json->>'dgs10_change_5d')::numeric as dgs10_change_5d,
  (feature_json->>'hy_oas_level')::numeric as hy_oas_level,
  (feature_json->>'hy_oas_change_1d')::numeric as hy_oas_change_1d,
  (feature_json->>'hy_oas_change_5d')::numeric as hy_oas_change_5d,
  ((feature_json->>'liquidity_expanding')::numeric)::int as liquidity_expanding,
  (feature_json->>'fed_balance_sheet_change_pct')::numeric as fed_bs_chg_pct,
  (feature_json->>'rrp_level')::numeric as rrp_level,
  (feature_json->>'rrp_change_pct_5d')::numeric as rrp_chg_pct_5d,
  
  -- VIX features
  (feature_json->>'vix_level')::numeric as vix_level,
  (feature_json->>'vix_change_1d')::numeric as vix_change_1d,
  (feature_json->>'vix_change_5d')::numeric as vix_change_5d,
  (feature_json->>'vix_term_structure')::numeric as vix_term_structure,
  
  -- Cross-asset features (returns and relative strength)
  (feature_json->>'dxy_ret_5d')::numeric as dxy_ret_5d,
  (feature_json->>'gold_ret_5d')::numeric as gold_ret_5d,
  (feature_json->>'oil_ret_5d')::numeric as oil_ret_5d,
  (feature_json->>'hyg_ret_5d')::numeric as hyg_ret_5d,
  (feature_json->>'hyg_vs_spy_5d')::numeric as hyg_vs_spy_5d,
  (feature_json->>'hyg_spy_corr_20d')::numeric as hyg_spy_corr_20d,
  (feature_json->>'lqd_ret_5d')::numeric as lqd_ret_5d,
  (feature_json->>'tlt_ret_5d')::numeric as tlt_ret_5d,
  
  -- Breadth features
  (feature_json->>'rsp_spy_ratio')::numeric as rsp_spy_ratio,
  (feature_json->>'rsp_spy_ratio_z')::numeric as rsp_spy_ratio_z,
  (feature_json->>'qqq_spy_ratio_z')::numeric as qqq_spy_ratio_z,
  (feature_json->>'iwm_spy_ratio_z')::numeric as iwm_spy_ratio_z,
  
  -- Event flags (pruned to 3 types) - FIXED: numeric -> int to handle "1.0" strings
  ((feature_json->>'is_fomc')::numeric)::int as is_fomc,
  ((feature_json->>'is_cpi_release')::numeric)::int as is_cpi_release,
  ((feature_json->>'is_nfp_release')::numeric)::int as is_nfp_release,
  
  created_at
from public.features_daily;

comment on view public.v_features_pruned is 'Pruned feature set: high-signal, low-collinearity features only';

commit;
