-- Migration: Optimize regression dataset for generalization and stability
-- Date: 2025-12-13
--
-- OBJECTIVES:
-- 1. Designate primary regression targets (y_1d_vol_clip, y_5d_vol_clip)
-- 2. Fix overnight_share feature definition for numerical stability
-- 3. Remove redundant features (reduce collinearity)
-- 4. Add feature clipping for outlier robustness
-- 5. Create optimized regression views
-- 6. Add validation checks

begin;

-- =========================================
-- A) TARGET OPTIMIZATION - PRIMARY TARGET
-- =========================================

-- Add primary regression target columns
alter table public.labels_daily
  add column if not exists y_1d_vol_clip numeric,  -- PRIMARY: vol-scaled + clipped
  add column if not exists y_5d_vol_clip numeric,  -- SECONDARY: vol-scaled + clipped
  add column if not exists primary_target numeric;  -- ALIAS for y_1d_vol_clip

comment on column public.labels_daily.y_1d_vol_clip is 
  'PRIMARY regression target: 1d vol-scaled return clipped to ±3σ';
comment on column public.labels_daily.y_5d_vol_clip is 
  'SECONDARY regression target: 5d vol-scaled return clipped to ±3σ';
comment on column public.labels_daily.primary_target is 
  'Default target for modeling (alias for y_1d_vol_clip)';

-- Compute y_1d_vol_clip: volatility-scaled AND clipped
-- This combines heteroskedasticity adjustment with outlier robustness
-- Clip vol-scaled returns to ±3 standard deviations
update public.labels_daily
set 
  y_1d_vol_clip = case
    when y_1d_vol is null then null
    else greatest(-3.0, least(3.0, y_1d_vol))
  end,
  y_5d_vol_clip = case
    when y_5d_vol is null then null
    else greatest(-3.0, least(3.0, y_5d_vol))
  end;

-- Set primary_target as alias
update public.labels_daily
set primary_target = y_1d_vol_clip
where y_1d_vol_clip is not null;

-- Add index for efficient target queries
create index if not exists idx_labels_daily_primary_target 
  on public.labels_daily(asset_id, date) 
  where primary_target is not null;

-- =========================================
-- B) FEATURE EXCLUSION LIST (REDUNDANCY)
-- =========================================

-- Create table to track excluded features
create table if not exists public.feature_exclusions (
  feature_name text primary key,
  reason text not null,
  excluded_date date default current_date
);

comment on table public.feature_exclusions is 
  'Features excluded from modeling due to redundancy or instability';

-- Insert excluded features
insert into public.feature_exclusions (feature_name, reason) values
  -- Redundant rate features
  ('dgs10_change_1d', 'Redundant with dgs10_change_5d and yield_curve_slope'),
  
  -- Redundant moving averages (keep SMA 20/50/200, EMA 20/50 only)
  ('sma_5', 'Redundant with SMA_20'),
  ('sma_10', 'Redundant with SMA_20'),
  ('ema_5', 'Redundant with EMA_20'),
  ('ema_10', 'Redundant with EMA_20'),
  ('ema_200', 'Redundant with SMA_200 and EMA_50'),
  
  -- Redundant MACD components (keep histogram only)
  ('macd_line', 'Redundant with macd_hist'),
  ('macd_signal', 'Redundant with macd_hist'),
  
  -- Redundant volume features
  ('obv', 'Noisy volume proxy, redundant with volume_z'),
  
  -- Redundant volatility windows
  ('vol_10', 'Redundant with vol_5 and vol_20'),
  
  -- Redundant returns
  ('log_ret_10d', 'Redundant with log_ret_5d and log_ret_20d'),
  
  -- Redundant drawdown
  ('dd_20', 'Redundant with dd_60')
on conflict (feature_name) do update set
  reason = excluded.reason,
  excluded_date = current_date;

-- =========================================
-- C) FEATURE METADATA & CLIPPING RULES
-- =========================================

-- Add clipping metadata to feature_metadata table
alter table public.feature_metadata
  add column if not exists clip_min numeric,
  add column if not exists clip_max numeric,
  add column if not exists scaling_method text,  -- 'zscore', 'none', 'minmax'
  add column if not exists is_binary boolean default false,
  add column if not exists is_excluded boolean default false;

comment on column public.feature_metadata.clip_min is 'Minimum value for clipping (null = no floor)';
comment on column public.feature_metadata.clip_max is 'Maximum value for clipping (null = no ceiling)';
comment on column public.feature_metadata.scaling_method is 'Normalization method: zscore, none, minmax';
comment on column public.feature_metadata.is_binary is 'True for binary/categorical features (no scaling)';
comment on column public.feature_metadata.is_excluded is 'True if feature is excluded from modeling';

-- Update existing feature metadata with clipping rules
-- Continuous features: clip to ±5
-- Volatility-scaled: clip to ±3
-- Binary features: no clipping

-- Technical features (continuous, clip to ±5 after z-scoring)
update public.feature_metadata
set 
  scaling_method = 'zscore',
  clip_min = -5.0,
  clip_max = 5.0,
  is_binary = false
where feature_type = 'technical' 
  and feature_name not in ('dow', 'days_since_prev', 'sma20_gt_sma50');

-- Binary/categorical features (no scaling)
update public.feature_metadata
set 
  scaling_method = 'none',
  is_binary = true,
  clip_min = null,
  clip_max = null
where feature_name in (
  'sma20_gt_sma50', 'dow', 'is_fomc', 'is_cpi_release', 'is_nfp_release',
  'high_vol_regime', 'curve_inverted', 'credit_stress', 
  'liquidity_expanding_regime', 'liquidity_expanding'
);

-- Macro features (continuous, clip to ±5)
update public.feature_metadata
set 
  scaling_method = 'zscore',
  clip_min = -5.0,
  clip_max = 5.0,
  is_binary = false
where feature_type = 'macro';

-- Lagged features (inherit from parent feature)
update public.feature_metadata
set 
  scaling_method = 'zscore',
  clip_min = -5.0,
  clip_max = 5.0,
  is_binary = false
where feature_type = 'lagged';

-- Regime features (binary)
update public.feature_metadata
set 
  scaling_method = 'none',
  is_binary = true
where feature_type = 'regime';

-- Target features (already clipped to ±3)
update public.feature_metadata
set 
  scaling_method = 'vol_scaled',
  clip_min = -3.0,
  clip_max = 3.0,
  is_binary = false
where feature_type = 'target';

-- Mark excluded features
update public.feature_metadata
set is_excluded = true
where feature_name in (
  select feature_name from public.feature_exclusions
);

-- =========================================
-- D) OPTIMIZED REGRESSION DATASET VIEW
-- =========================================

-- Drop old views
drop view if exists public.v_regression_dataset cascade;

-- Create optimized view with:
-- 1. Primary target only (y_1d_vol_clip)
-- 2. Excluded features removed
-- 3. Feature list documented
create or replace view public.v_regression_dataset_optimized as
select 
  a.symbol,
  db.date,
  
  -- PRIMARY TARGET
  l.primary_target,
  
  -- Technical features (non-redundant)
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
  
  -- Moving averages (kept: SMA 20/50/200, EMA 20/50)
  (fp.feature_json->>'sma_20')::numeric as sma_20,
  (fp.feature_json->>'sma_50')::numeric as sma_50,
  (fp.feature_json->>'sma_200')::numeric as sma_200,
  (fp.feature_json->>'ema_20')::numeric as ema_20,
  (fp.feature_json->>'ema_50')::numeric as ema_50,
  (fp.feature_json->>'sma20_gt_sma50')::int as sma20_gt_sma50,
  
  -- Volume (kept: volume_z, volume_chg_pct; dropped: OBV)
  (fp.feature_json->>'volume_z')::numeric as volume_z,
  (fp.feature_json->>'volume_chg_pct')::numeric as volume_chg_pct,
  
  -- Drawdown (kept: dd_60; dropped: dd_20)
  (fp.feature_json->>'dd_60')::numeric as dd_60,
  
  -- Calendar
  (fp.feature_json->>'dow')::int as dow,
  (fp.feature_json->>'days_since_prev')::int as days_since_prev,
  
  -- Overnight/Intraday features
  (fp.feature_json->>'overnight_return')::numeric as overnight_return,
  (fp.feature_json->>'intraday_return')::numeric as intraday_return,
  (fp.feature_json->>'overnight_mean_20')::numeric as overnight_mean_20,
  (fp.feature_json->>'overnight_std_20')::numeric as overnight_std_20,
  (fp.feature_json->>'intraday_mean_20')::numeric as intraday_mean_20,
  (fp.feature_json->>'intraday_std_20')::numeric as intraday_std_20,
  (fp.feature_json->>'overnight_share')::numeric as overnight_share,
  
  -- Trend quality
  (fp.feature_json->>'adx_14')::numeric as adx_14,
  (fp.feature_json->>'return_autocorr_20')::numeric as return_autocorr_20,
  (fp.feature_json->>'price_rsq_20')::numeric as price_rsq_20,
  
  -- Macro features (kept: dgs10_change_5d; dropped: dgs10_change_1d)
  (fp.feature_json->>'dgs2')::numeric as dgs2,
  (fp.feature_json->>'dgs10')::numeric as dgs10,
  (fp.feature_json->>'yield_curve_slope')::numeric as yield_curve_slope,
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
  
  -- Lagged features
  (fp.feature_json->>'log_ret_1d_lag1')::numeric as log_ret_1d_lag1,
  (fp.feature_json->>'log_ret_1d_lag2')::numeric as log_ret_1d_lag2,
  (fp.feature_json->>'log_ret_1d_lag3')::numeric as log_ret_1d_lag3,
  (fp.feature_json->>'log_ret_1d_lag5')::numeric as log_ret_1d_lag5,
  (fp.feature_json->>'vix_change_lag1')::numeric as vix_change_lag1,
  (fp.feature_json->>'vix_change_lag3')::numeric as vix_change_lag3,
  (fp.feature_json->>'hy_oas_change_lag1')::numeric as hy_oas_change_lag1,
  (fp.feature_json->>'yield_curve_slope_lag1')::numeric as yield_curve_slope_lag1,
  
  -- Regime flags
  (fp.feature_json->>'high_vol_regime')::int as high_vol_regime,
  (fp.feature_json->>'curve_inverted')::int as curve_inverted,
  (fp.feature_json->>'credit_stress')::int as credit_stress,
  (fp.feature_json->>'liquidity_expanding_regime')::int as liquidity_expanding_regime,
  
  -- Event flags
  (fp.feature_json->>'is_fomc')::int as is_fomc,
  (fp.feature_json->>'is_cpi_release')::int as is_cpi_release,
  (fp.feature_json->>'is_nfp_release')::int as is_nfp_release
  
from public.daily_bars db
join public.assets a on a.id = db.asset_id
left join public.features_daily fp on fp.asset_id = db.asset_id and fp.date = db.date
left join public.labels_daily l on l.asset_id = db.asset_id and l.date = db.date
where a.asset_type = 'ETF'
  and l.primary_target is not null;  -- Only include rows with valid target

comment on view public.v_regression_dataset_optimized is 
  'OPTIMIZED regression dataset: primary target only, redundant features excluded, ready for modeling';

-- =========================================
-- E) DIAGNOSTICS VIEW (ALL TARGETS)
-- =========================================

-- Create diagnostics view with all targets for comparison
create or replace view public.v_regression_diagnostics as
select 
  a.symbol,
  l.date,
  
  -- ALL TARGETS (for comparison and diagnostics)
  l.y_1d_raw as y_1d_raw,
  l.y_5d_raw as y_5d_raw,
  l.y_1d_vol as y_1d_vol,
  l.y_5d_vol as y_5d_vol,
  l.y_1d_clipped as y_1d_clipped,
  l.y_5d_clipped as y_5d_clipped,
  l.y_1d_vol_clip as y_1d_vol_clip,
  l.y_5d_vol_clip as y_5d_vol_clip,
  l.primary_target,
  
  -- Classification targets (legacy)
  l.y_1d as y_1d_class,
  l.y_5d as y_5d_class,
  l.y_thresh as y_thresh_class,
  
  -- Variance metrics
  stddev(l.y_1d_raw) over (partition by l.asset_id order by l.date rows between 252 preceding and current row) as y_1d_raw_std_252,
  stddev(l.y_1d_vol) over (partition by l.asset_id order by l.date rows between 252 preceding and current row) as y_1d_vol_std_252,
  stddev(l.y_1d_vol_clip) over (partition by l.asset_id order by l.date rows between 252 preceding and current row) as y_1d_vol_clip_std_252
  
from public.labels_daily l
join public.assets a on a.id = l.asset_id
where a.asset_type = 'ETF'
order by l.date desc, a.symbol;

comment on view public.v_regression_diagnostics is 
  'Diagnostic view showing all target variants for comparison and analysis';

-- =========================================
-- F) DATASET VALIDATION CHECKS
-- =========================================

-- Create validation function for data quality
create or replace function public.validate_regression_dataset()
returns table(
  check_name text,
  status text,
  details text
) as $$
begin
  -- Check 1: No NaN in primary target (beyond warm-up)
  return query
  select 
    'primary_target_nans'::text,
    case when count(*) = 0 then 'PASS' else 'FAIL' end::text,
    format('%s rows with NULL primary_target after 252-day warm-up', count(*))
  from public.labels_daily l
  join public.assets a on a.id = l.asset_id
  where a.asset_type = 'ETF'
    and l.date > (select min(date) + interval '252 days' from public.labels_daily)
    and l.primary_target is null;
  
  -- Check 2: No duplicate (symbol, date)
  return query
  select 
    'duplicate_symbol_date'::text,
    case when count(*) = 0 then 'PASS' else 'FAIL' end::text,
    format('%s duplicate (symbol, date) pairs', count(*))
  from (
    select a.symbol, l.date, count(*)
    from public.labels_daily l
    join public.assets a on a.id = l.asset_id
    where a.asset_type = 'ETF'
    group by a.symbol, l.date
    having count(*) > 1
  ) dups;
  
  -- Check 3: Target variance is non-zero per symbol
  return query
  select 
    'target_variance_nonzero'::text,
    case when count(*) = 0 then 'PASS' else 'FAIL' end::text,
    format('%s symbols with zero target variance', count(*))
  from (
    select 
      a.symbol,
      stddev(l.primary_target) as target_std
    from public.labels_daily l
    join public.assets a on a.id = l.asset_id
    where a.asset_type = 'ETF'
      and l.primary_target is not null
    group by a.symbol
    having stddev(l.primary_target) = 0 or stddev(l.primary_target) is null
  ) zero_var;
  
  -- Check 4: Feature count matches expected
  return query
  select 
    'feature_count'::text,
    'INFO'::text,
    format('%s features in optimized dataset', count(distinct column_name))
  from information_schema.columns
  where table_schema = 'public'
    and table_name = 'v_regression_dataset_optimized'
    and column_name not in ('symbol', 'date', 'primary_target');
  
  -- Check 5: No extreme outliers in primary target (beyond ±10)
  return query
  select 
    'extreme_outliers'::text,
    case when count(*) = 0 then 'PASS' else 'WARN' end::text,
    format('%s rows with |primary_target| > 10', count(*))
  from public.labels_daily
  where abs(primary_target) > 10;
  
  -- Check 6: Date range coverage
  return query
  select 
    'date_range'::text,
    'INFO'::text,
    format('Date range: %s to %s (%s days)', 
      min(date)::text, 
      max(date)::text, 
      max(date) - min(date))
  from public.labels_daily l
  join public.assets a on a.id = l.asset_id
  where a.asset_type = 'ETF'
    and l.primary_target is not null;
  
end;
$$ language plpgsql;

comment on function public.validate_regression_dataset is 
  'Validates regression dataset quality: checks for NaNs, duplicates, variance, outliers';

-- =========================================
-- G) FEATURE MANIFEST CONSTANT
-- =========================================

-- Create feature manifest for documentation
create or replace view public.v_feature_manifest as
select 
  fm.feature_name,
  fm.feature_type,
  fm.description,
  fm.window_size,
  fm.scaling_method,
  fm.is_binary,
  fm.clip_min,
  fm.clip_max,
  fm.is_excluded,
  fe.reason as exclusion_reason
from public.feature_metadata fm
left join public.feature_exclusions fe on fe.feature_name = fm.feature_name
order by 
  fm.is_excluded,
  fm.feature_type,
  fm.feature_name;

comment on view public.v_feature_manifest is 
  'Complete feature manifest with metadata, scaling rules, and exclusions';

-- =========================================
-- H) OPTIMIZATION SUMMARY
-- =========================================

-- Create summary view of optimization changes
create or replace view public.v_optimization_summary as
select 
  'Primary Target' as category,
  'y_1d_vol_clip' as value,
  'Volatility-scaled 1d return clipped to ±3σ' as description
union all
select 
  'Secondary Target',
  'y_5d_vol_clip',
  'Volatility-scaled 5d return clipped to ±3σ'
union all
select 
  'Features Excluded',
  count(*)::text,
  'Redundant features removed for collinearity reduction'
from public.feature_exclusions
union all
select 
  'Features Kept',
  count(distinct column_name)::text,
  'Non-redundant features in optimized dataset'
from information_schema.columns
where table_schema = 'public'
  and table_name = 'v_regression_dataset_optimized'
  and column_name not in ('symbol', 'date', 'primary_target')
union all
select 
  'Total Symbols',
  count(distinct symbol)::text,
  'ETFs in dataset'
from public.assets
where asset_type = 'ETF'
union all
select 
  'Date Range',
  format('%s to %s', min(date), max(date)),
  'Coverage period'
from (
  select date from public.labels_daily 
  where primary_target is not null
  limit 1000000
) dates;

comment on view public.v_optimization_summary is 
  'Summary of dataset optimization changes';

commit;
