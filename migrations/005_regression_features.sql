-- Migration: Add regression-friendly features and targets
-- Adds: volatility-scaled targets, overnight/intraday splits, regime flags, lagged features
-- Date: 2025-12-13

begin;

-- =========================================
-- A) EXTEND LABELS_DAILY FOR REGRESSION TARGETS
-- =========================================

-- Add volatility-scaled regression targets
alter table public.labels_daily
  add column if not exists y_1d_raw numeric,
  add column if not exists y_5d_raw numeric,
  add column if not exists y_1d_vol numeric,  -- 1d return / rolling_vol_20
  add column if not exists y_5d_vol numeric,  -- 5d return / rolling_vol_20
  add column if not exists y_1d_clipped numeric,  -- clipped to ±3 std
  add column if not exists y_5d_clipped numeric;  -- clipped to ±3 std

comment on column public.labels_daily.y_1d_raw is '1-day forward log return (raw)';
comment on column public.labels_daily.y_5d_raw is '5-day forward log return (raw)';
comment on column public.labels_daily.y_1d_vol is '1-day forward return scaled by 20d realized vol (heteroskedasticity-adjusted)';
comment on column public.labels_daily.y_5d_vol is '5-day forward return scaled by 20d realized vol (heteroskedasticity-adjusted)';
comment on column public.labels_daily.y_1d_clipped is '1-day return clipped to ±3 std (robustness)';
comment on column public.labels_daily.y_5d_clipped is '5-day return clipped to ±3 std (robustness)';

-- =========================================
-- B) ADD INDEXES FOR REGRESSION QUERIES
-- =========================================

-- Index for time-series queries (date range scans)
create index if not exists idx_features_daily_date 
  on public.features_daily(date);

create index if not exists idx_labels_daily_date 
  on public.labels_daily(date);

-- Composite index for symbol + date queries
create index if not exists idx_features_daily_asset_date 
  on public.features_daily(asset_id, date);

create index if not exists idx_labels_daily_asset_date 
  on public.labels_daily(asset_id, date);

-- =========================================
-- C) ADD HELPER FUNCTION FOR VOL SCALING
-- =========================================

-- Compute volatility-scaled target
create or replace function public.compute_vol_scaled_target(
  p_return numeric,
  p_vol numeric
)
returns numeric as $$
begin
  if p_vol is null or p_vol <= 0 then
    return null;
  end if;
  return p_return / p_vol;
end;
$$ language plpgsql immutable;

comment on function public.compute_vol_scaled_target is 
  'Scale return by realized volatility for heteroskedasticity adjustment';

-- =========================================
-- D) CREATE REGRESSION MODEL VIEW
-- =========================================

-- Drop old view if exists
drop view if exists public.v_regression_dataset cascade;

-- Create new regression dataset view
-- This will be updated after we add all features
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
  (fp.feature_json->>'sma_200')::numeric as sma_200,
  (fp.feature_json->>'ema_20')::numeric as ema_20,
  (fp.feature_json->>'ema_50')::numeric as ema_50,
  (fp.feature_json->>'sma20_gt_sma50')::int as sma20_gt_sma50,
  (fp.feature_json->>'volume_z')::numeric as volume_z,
  (fp.feature_json->>'volume_chg_pct')::numeric as volume_chg_pct,
  (fp.feature_json->>'dd_60')::numeric as dd_60,
  (fp.feature_json->>'dow')::int as dow,
  (fp.feature_json->>'days_since_prev')::int as days_since_prev,
  
  -- Overnight/Intraday features (will be added)
  (fp.feature_json->>'overnight_return')::numeric as overnight_return,
  (fp.feature_json->>'intraday_return')::numeric as intraday_return,
  (fp.feature_json->>'overnight_mean_20')::numeric as overnight_mean_20,
  (fp.feature_json->>'overnight_std_20')::numeric as overnight_std_20,
  (fp.feature_json->>'intraday_mean_20')::numeric as intraday_mean_20,
  (fp.feature_json->>'intraday_std_20')::numeric as intraday_std_20,
  (fp.feature_json->>'overnight_share')::numeric as overnight_share,
  
  -- Trend quality features (will be added)
  (fp.feature_json->>'adx_14')::numeric as adx_14,
  (fp.feature_json->>'return_autocorr_20')::numeric as return_autocorr_20,
  (fp.feature_json->>'price_rsq_20')::numeric as price_rsq_20,
  
  -- Macro features
  (fp.feature_json->>'dgs2')::numeric as dgs2,
  (fp.feature_json->>'dgs10')::numeric as dgs10,
  (fp.feature_json->>'yield_curve_slope')::numeric as yield_curve_slope,
  (fp.feature_json->>'dgs10_change_1d')::numeric as dgs10_change_1d,
  (fp.feature_json->>'dgs10_change_5d')::numeric as dgs10_change_5d,
  (fp.feature_json->>'hy_oas_level')::numeric as hy_oas_level,
  (fp.feature_json->>'hy_oas_change_1d')::numeric as hy_oas_change_1d,
  (fp.feature_json->>'hy_oas_change_5d')::numeric as hy_oas_change_5d,
  (fp.feature_json->>'liquidity_expanding')::int as liquidity_expanding,
  (fp.feature_json->>'fed_bs_chg_pct')::numeric as fed_bs_chg_pct,
  (fp.feature_json->>'rrp_level')::numeric as rrp_level,
  (fp.feature_json->>'rrp_chg_pct_5d')::numeric as rrp_chg_pct_5d,
  
  -- VIX features
  (fp.feature_json->>'vix_level')::numeric as vix_level,
  (fp.feature_json->>'vix_change_1d')::numeric as vix_change_1d,
  (fp.feature_json->>'vix_change_5d')::numeric as vix_change_5d,
  (fp.feature_json->>'vix_term_structure')::numeric as vix_term_structure,
  
  -- Cross-asset features
  (fp.feature_json->>'dxy_ret_5d')::numeric as dxy_ret_5d,
  (fp.feature_json->>'gold_ret_5d')::numeric as gold_ret_5d,
  (fp.feature_json->>'oil_ret_5d')::numeric as oil_ret_5d,
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
  
  -- Lagged features (will be added)
  (fp.feature_json->>'log_ret_1d_lag1')::numeric as log_ret_1d_lag1,
  (fp.feature_json->>'log_ret_1d_lag2')::numeric as log_ret_1d_lag2,
  (fp.feature_json->>'log_ret_1d_lag3')::numeric as log_ret_1d_lag3,
  (fp.feature_json->>'log_ret_1d_lag5')::numeric as log_ret_1d_lag5,
  (fp.feature_json->>'vix_change_lag1')::numeric as vix_change_lag1,
  (fp.feature_json->>'vix_change_lag3')::numeric as vix_change_lag3,
  (fp.feature_json->>'hy_oas_change_lag1')::numeric as hy_oas_change_lag1,
  (fp.feature_json->>'yield_curve_slope_lag1')::numeric as yield_curve_slope_lag1,
  
  -- Regime flags (will be added)
  (fp.feature_json->>'high_vol_regime')::int as high_vol_regime,
  (fp.feature_json->>'curve_inverted')::int as curve_inverted,
  (fp.feature_json->>'credit_stress')::int as credit_stress,
  (fp.feature_json->>'liquidity_expanding_regime')::int as liquidity_expanding_regime,
  
  -- Event flags
  (fp.feature_json->>'is_fomc')::int as is_fomc,
  (fp.feature_json->>'is_cpi_release')::int as is_cpi_release,
  (fp.feature_json->>'is_nfp_release')::int as is_nfp_release,
  
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

-- =========================================
-- E) ADD METADATA TRACKING
-- =========================================

-- Track feature computation metadata
create table if not exists public.feature_metadata (
  id bigserial primary key,
  feature_name text not null,
  feature_type text not null,  -- 'technical', 'macro', 'lagged', 'regime'
  description text,
  window_size int,  -- rolling window if applicable
  created_at timestamptz default now()
);

comment on table public.feature_metadata is 
  'Tracks feature definitions and computation parameters for documentation';

-- Insert feature metadata
insert into public.feature_metadata (feature_name, feature_type, description, window_size) values
  ('overnight_return', 'technical', 'Open - previous close', null),
  ('intraday_return', 'technical', 'Close - open', null),
  ('overnight_mean_20', 'technical', '20-day mean of overnight returns', 20),
  ('overnight_std_20', 'technical', '20-day std of overnight returns', 20),
  ('intraday_mean_20', 'technical', '20-day mean of intraday returns', 20),
  ('intraday_std_20', 'technical', '20-day std of intraday returns', 20),
  ('overnight_share', 'technical', 'Overnight return / total daily return', null),
  ('adx_14', 'technical', '14-day Average Directional Index (trend strength)', 14),
  ('return_autocorr_20', 'technical', '20-day autocorrelation of returns', 20),
  ('price_rsq_20', 'technical', '20-day R² of price vs time (linear trend fit)', 20),
  ('log_ret_1d_lag1', 'lagged', '1-day return lagged 1 period', null),
  ('log_ret_1d_lag2', 'lagged', '1-day return lagged 2 periods', null),
  ('log_ret_1d_lag3', 'lagged', '1-day return lagged 3 periods', null),
  ('log_ret_1d_lag5', 'lagged', '1-day return lagged 5 periods', null),
  ('vix_change_lag1', 'lagged', 'VIX 1d change lagged 1 period', null),
  ('vix_change_lag3', 'lagged', 'VIX 1d change lagged 3 periods', null),
  ('hy_oas_change_lag1', 'lagged', 'HY OAS 1d change lagged 1 period', null),
  ('yield_curve_slope_lag1', 'lagged', 'Yield curve slope lagged 1 period', null),
  ('high_vol_regime', 'regime', 'VIX > 20 OR VIX > 75th percentile (60d)', 60),
  ('curve_inverted', 'regime', 'DGS10 < DGS2 (inverted yield curve)', null),
  ('credit_stress', 'regime', 'HY OAS > 80th percentile (60d)', 60),
  ('liquidity_expanding_regime', 'regime', 'Fed balance sheet 4-week change > 0', 20),
  ('y_1d_vol', 'target', '1d return / rolling_vol_20 (vol-scaled regression target)', 20),
  ('y_5d_vol', 'target', '5d return / rolling_vol_20 (vol-scaled regression target)', 20)
on conflict do nothing;

commit;
