-- Migration: Add 1-day classification support (Triple Barrier Method)
-- Date: 2025-12-14
--
-- OBJECTIVES:
-- 1. Add y_class_1d target using volatility-aware thresholds
-- 2. Create classification-specific view (v_classification_dataset_1d)
-- 3. Add class distribution diagnostics (v_classification_stats_1d)
-- 4. Add validation function for classification data quality
--
-- IMPORTANT: Preserves all existing regression infrastructure

begin;

-- =========================================
-- A) CLASSIFICATION TARGET - TRIPLE BARRIER
-- =========================================

-- Add classification target column to labels_daily
alter table public.labels_daily
  add column if not exists y_class_1d int;

comment on column public.labels_daily.y_class_1d is 
  'Triple-barrier classification target: 1 (Buy), 0 (Hold), -1 (Sell) based on y_1d_vol thresholds (±0.25)';

-- Compute y_class_1d using volatility-scaled returns
-- This separates signal from noise better than raw direction
update public.labels_daily
set y_class_1d = case
  when y_1d_vol is null then null
  when y_1d_vol > 0.25 then 1   -- Significant up move (Buy)
  when y_1d_vol < -0.25 then -1  -- Significant down move (Sell)
  else 0                         -- Noise/chop range (Hold)
end;

-- Add index for classification queries
create index if not exists idx_labels_daily_y_class_1d 
  on public.labels_daily(asset_id, date) 
  where y_class_1d is not null;

-- =========================================
-- B) CLASSIFICATION DATASET VIEW
-- =========================================

-- Create classification-specific view
-- Includes ONLY the classification target, NO regression targets
create or replace view public.v_classification_dataset_1d as
select 
  a.symbol,
  db.date,
  
  -- CLASSIFICATION TARGET (ONLY)
  l.y_class_1d,
  
  -- Technical features (identical to regression dataset)
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
  
  -- Moving averages
  (fp.feature_json->>'sma_20')::numeric as sma_20,
  (fp.feature_json->>'sma_50')::numeric as sma_50,
  (fp.feature_json->>'sma_200')::numeric as sma_200,
  (fp.feature_json->>'ema_20')::numeric as ema_20,
  (fp.feature_json->>'ema_50')::numeric as ema_50,
  (fp.feature_json->>'sma20_gt_sma50')::int as sma20_gt_sma50,
  
  -- Volume
  (fp.feature_json->>'volume_z')::numeric as volume_z,
  (fp.feature_json->>'volume_chg_pct')::numeric as volume_chg_pct,
  
  -- Drawdown
  (fp.feature_json->>'dd_60')::numeric as dd_60,
  
  -- Calendar
  (fp.feature_json->>'dow')::int as dow,
  (fp.feature_json->>'days_since_prev')::int as days_since_prev,
  
  -- Overnight/Intraday
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
  
  -- Macro features
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
  and l.y_class_1d is not null;  -- Only include rows with valid classification target

comment on view public.v_classification_dataset_1d is 
  'Classification dataset for 1-day prediction: y_class_1d (Buy/Hold/Sell) + 83 features. Hold class (0) included for anti-overtrading.';

-- =========================================
-- C) CLASS DISTRIBUTION DIAGNOSTICS
-- =========================================

-- Create diagnostics view to monitor class balance
create or replace view public.v_classification_stats_1d as
select 
  a.symbol,
  count(*) as total_rows,
  sum(case when l.y_class_1d = 1 then 1 else 0 end) as count_buy,
  sum(case when l.y_class_1d = -1 then 1 else 0 end) as count_sell,
  sum(case when l.y_class_1d = 0 then 1 else 0 end) as count_hold,
  round(100.0 * sum(case when l.y_class_1d = 1 then 1 else 0 end) / count(*), 2) as pct_buy,
  round(100.0 * sum(case when l.y_class_1d = -1 then 1 else 0 end) / count(*), 2) as pct_sell,
  round(100.0 * sum(case when l.y_class_1d = 0 then 1 else 0 end) / count(*), 2) as pct_hold
from public.labels_daily l
join public.assets a on a.id = l.asset_id
where a.asset_type = 'ETF'
  and l.y_class_1d is not null
group by a.symbol
order by a.symbol;

comment on view public.v_classification_stats_1d is 
  'Class distribution statistics per symbol. WARNING if pct_hold > 85% (threshold too strict).';

-- Overall stats (all symbols combined)
create or replace view public.v_classification_stats_1d_overall as
select 
  'ALL' as symbol,
  count(*) as total_rows,
  sum(case when l.y_class_1d = 1 then 1 else 0 end) as count_buy,
  sum(case when l.y_class_1d = -1 then 1 else 0 end) as count_sell,
  sum(case when l.y_class_1d = 0 then 1 else 0 end) as count_hold,
  round(100.0 * sum(case when l.y_class_1d = 1 then 1 else 0 end) / count(*), 2) as pct_buy,
  round(100.0 * sum(case when l.y_class_1d = -1 then 1 else 0 end) / count(*), 2) as pct_sell,
  round(100.0 * sum(case when l.y_class_1d = 0 then 1 else 0 end) / count(*), 2) as pct_hold
from public.labels_daily l
join public.assets a on a.id = l.asset_id
where a.asset_type = 'ETF'
  and l.y_class_1d is not null;

comment on view public.v_classification_stats_1d_overall is 
  'Overall class distribution across all symbols';

-- =========================================
-- D) VALIDATION FUNCTION
-- =========================================

-- Create validation function for classification dataset
create or replace function public.validate_classification_dataset_1d()
returns table(
  check_name text,
  status text,
  details text
) as $$
begin
  -- Check 1: No NULL targets (beyond warm-up period)
  return query
  select 
    'no_null_targets'::text,
    case when count(*) = 0 then 'PASS' else 'FAIL' end::text,
    format('%s rows with NULL y_class_1d after 252-day warm-up', count(*))
  from public.labels_daily l
  join public.assets a on a.id = l.asset_id
  where a.asset_type = 'ETF'
    and l.date > (select min(date) + interval '252 days' from public.labels_daily)
    and l.y_class_1d is null
    and l.y_1d_vol is not null;  -- Should have target if y_1d_vol exists
  
  -- Check 2: Valid class values only (-1, 0, 1)
  return query
  select 
    'valid_class_values'::text,
    case when count(*) = 0 then 'PASS' else 'FAIL' end::text,
    format('%s rows with invalid class values (not in -1, 0, 1)', count(*))
  from public.labels_daily l
  join public.assets a on a.id = l.asset_id
  where a.asset_type = 'ETF'
    and l.y_class_1d is not null
    and l.y_class_1d not in (-1, 0, 1);
  
  -- Check 3: Class balance warning (Hold class > 85%)
  return query
  select 
    'class_balance'::text,
    case 
      when max(pct_hold) > 85 then 'WARN'
      when max(pct_hold) > 90 then 'FAIL'
      else 'PASS' 
    end::text,
    format('Hold class percentage: %.2f%% (WARNING if > 85%%, FAIL if > 90%%)', max(pct_hold))
  from (
    select 
      100.0 * sum(case when l.y_class_1d = 0 then 1 else 0 end) / count(*) as pct_hold
    from public.labels_daily l
    join public.assets a on a.id = l.asset_id
    where a.asset_type = 'ETF'
      and l.y_class_1d is not null
  ) stats;
  
  -- Check 4: No duplicate (symbol, date)
  return query
  select 
    'no_duplicates'::text,
    case when count(*) = 0 then 'PASS' else 'FAIL' end::text,
    format('%s duplicate (symbol, date) pairs', count(*))
  from (
    select a.symbol, l.date, count(*)
    from public.labels_daily l
    join public.assets a on a.id = l.asset_id
    where a.asset_type = 'ETF'
      and l.y_class_1d is not null
    group by a.symbol, l.date
    having count(*) > 1
  ) dups;
  
  -- Check 5: Feature count matches expected
  return query
  select 
    'feature_count'::text,
    'INFO'::text,
    format('%s features in classification dataset', count(distinct column_name))
  from information_schema.columns
  where table_schema = 'public'
    and table_name = 'v_classification_dataset_1d'
    and column_name not in ('symbol', 'date', 'y_class_1d');
  
  -- Check 6: Row count per symbol
  return query
  select 
    'row_count_per_symbol'::text,
    'INFO'::text,
    format('%s symbols with avg %.0f rows each', 
      count(distinct a.symbol),
      avg(cnt))
  from (
    select a.symbol, count(*) as cnt
    from public.labels_daily l
    join public.assets a on a.id = l.asset_id
    where a.asset_type = 'ETF'
      and l.y_class_1d is not null
    group by a.symbol
  ) per_symbol
  join public.assets a on true
  where a.asset_type = 'ETF';
  
  -- Check 7: Class distribution per symbol
  return query
  select 
    'class_distribution'::text,
    'INFO'::text,
    format('Buy: %.1f%%, Hold: %.1f%%, Sell: %.1f%%',
      avg(pct_buy), avg(pct_hold), avg(pct_sell))
  from public.v_classification_stats_1d;
  
end;
$$ language plpgsql;

comment on function public.validate_classification_dataset_1d is 
  'Validates classification dataset: no nulls, valid classes, balance check, no duplicates';

-- =========================================
-- E) UPDATE OPTIMIZATION SUMMARY
-- =========================================

-- Extend optimization summary to include classification info
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
  'Classification Target',
  'y_class_1d',
  'Triple-barrier 1d class: 1 (Buy), 0 (Hold), -1 (Sell) using y_1d_vol ± 0.25'
union all
-- Features Excluded count (requires migration 007 - feature_exclusions table)
-- Uncomment below after running migration 007:
-- select 'Features Excluded', count(*)::text, 'Redundant features removed'
-- from public.feature_exclusions
-- union all
select 
  'Features Kept',
  count(distinct column_name)::text,
  'Non-redundant features in optimized datasets'
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
  where y_class_1d is not null
  limit 1000000
) dates
union all
select 
  'Classification Rows',
  count(*)::text,
  'Total rows with valid y_class_1d target'
from public.labels_daily l
join public.assets a on a.id = l.asset_id
where a.asset_type = 'ETF'
  and l.y_class_1d is not null;

comment on view public.v_optimization_summary is 
  'Summary of dataset optimization changes (regression + classification)';

commit;
