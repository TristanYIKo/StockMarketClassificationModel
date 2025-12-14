-- Migration: Prune low-ROI features and event types
-- Remove redundant features and restrict event calendar to high-signal macro releases only
-- Date: 2025-12-13

begin;

-- =========================================
-- A) EVENT CALENDAR PRUNING
-- =========================================

-- Delete low-ROI event types (options expiry, month-end, quarter-end)
delete from public.events_calendar 
where event_type in ('options_expiry_week', 'month_end', 'quarter_end');

-- Add CHECK constraint to allow only high-ROI macro release events
alter table public.events_calendar
  drop constraint if exists chk_events_calendar_event_type;

alter table public.events_calendar
  add constraint chk_events_calendar_event_type 
  check (event_type in ('fomc', 'cpi_release', 'nfp_release'));

comment on constraint chk_events_calendar_event_type on public.events_calendar 
  is 'Only allow high-ROI macro release event types: FOMC, CPI, NFP';

-- =========================================
-- B) CREATE PRUNED FEATURES VIEW
-- =========================================

-- Create a view that extracts only the kept features from feature_json
-- This is safer than dropping JSONB keys and allows rollback
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
  (feature_json->>'sma20_gt_sma50')::int as sma20_gt_sma50,
  
  -- Volume (keep zscore and change; drop OBV)
  (feature_json->>'volume_z')::numeric as volume_z,
  (feature_json->>'volume_chg_pct')::numeric as volume_chg_pct,
  
  -- Drawdown (keep 60d only; drop 20d)
  (feature_json->>'dd_60')::numeric as dd_60,
  
  -- Calendar (keep day_of_week and days_since_prev; drop month)
  (feature_json->>'dow')::int as dow,
  (feature_json->>'days_since_prev')::int as days_since_prev,
  
  -- Macro features (kept as-is from context merge)
  (feature_json->>'DGS2')::numeric as dgs2,
  (feature_json->>'DGS10')::numeric as dgs10,
  (feature_json->>'yield_curve_slope')::numeric as yield_curve_slope,
  (feature_json->>'dgs10_change_1d')::numeric as dgs10_change_1d,
  (feature_json->>'dgs10_change_5d')::numeric as dgs10_change_5d,
  (feature_json->>'hy_oas_level')::numeric as hy_oas_level,
  (feature_json->>'hy_oas_change_1d')::numeric as hy_oas_change_1d,
  (feature_json->>'hy_oas_change_5d')::numeric as hy_oas_change_5d,
  (feature_json->>'liquidity_expanding')::int as liquidity_expanding,
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
  
  -- Event flags (pruned to 3 types)
  (feature_json->>'is_fomc')::int as is_fomc,
  (feature_json->>'is_cpi_release')::int as is_cpi_release,
  (feature_json->>'is_nfp_release')::int as is_nfp_release,
  
  created_at
from public.features_daily;

comment on view public.v_features_pruned is 'Pruned feature set: high-signal, low-collinearity features only';

-- =========================================
-- C) UPDATE MODEL DATASET VIEW (PRUNED)
-- =========================================

drop view if exists public.v_model_dataset_enhanced;
drop view if exists public.v_model_dataset cascade;

create or replace view public.v_model_dataset as
select 
  a.symbol,
  db.date,
  db.open, 
  db.high, 
  db.low, 
  db.close, 
  db.adj_close, 
  db.volume,
  
  -- Technical features (pruned set)
  fp.log_ret_1d,
  fp.log_ret_5d,
  fp.log_ret_20d,
  fp.rsi_14,
  fp.macd_hist,
  fp.vol_5,
  fp.vol_20,
  fp.vol_60,
  fp.atr_14,
  fp.high_low_pct,
  fp.close_open_pct,
  fp.sma_20,
  fp.sma_50,
  fp.sma_200,
  fp.ema_20,
  fp.ema_50,
  fp.sma20_gt_sma50,
  fp.volume_z,
  fp.volume_chg_pct,
  fp.dd_60,
  fp.dow,
  fp.days_since_prev,
  
  -- Macro features
  fp.dgs2,
  fp.dgs10,
  fp.yield_curve_slope,
  fp.dgs10_change_1d,
  fp.dgs10_change_5d,
  fp.hy_oas_level,
  fp.hy_oas_change_1d,
  fp.hy_oas_change_5d,
  fp.liquidity_expanding,
  fp.fed_bs_chg_pct,
  fp.rrp_level,
  fp.rrp_chg_pct_5d,
  
  -- VIX features
  fp.vix_level,
  fp.vix_change_1d,
  fp.vix_change_5d,
  fp.vix_term_structure,
  
  -- Cross-asset features
  fp.dxy_ret_5d,
  fp.gold_ret_5d,
  fp.oil_ret_5d,
  fp.hyg_ret_5d,
  fp.hyg_vs_spy_5d,
  fp.hyg_spy_corr_20d,
  fp.lqd_ret_5d,
  fp.tlt_ret_5d,
  
  -- Breadth features
  fp.rsp_spy_ratio,
  fp.rsp_spy_ratio_z,
  fp.qqq_spy_ratio_z,
  fp.iwm_spy_ratio_z,
  
  -- Event flags (only 3 high-ROI types)
  fp.is_fomc,
  fp.is_cpi_release,
  fp.is_nfp_release,
  
  -- Labels
  l.y_1d, 
  l.y_5d, 
  l.y_thresh
  
from public.daily_bars db
join public.assets a on a.id = db.asset_id
left join public.v_features_pruned fp on fp.asset_id = db.asset_id and fp.date = db.date
left join public.labels_daily l on l.asset_id = db.asset_id and l.date = db.date
where a.asset_type = 'ETF';

comment on view public.v_model_dataset is 'Modeling dataset with pruned features (60 features total)';

commit;
