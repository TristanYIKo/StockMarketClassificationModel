-- Example SQL Queries for Classification Model
-- Use these queries in Supabase SQL Editor or psql

-- =====================================================
-- 1. CHECK CLASS DISTRIBUTION (per symbol)
-- =====================================================
select * from public.v_classification_stats_1d
order by symbol;

-- Expected: Buy ~42%, Sell ~36%, Hold ~22%


-- =====================================================
-- 2. OVERALL CLASS DISTRIBUTION
-- =====================================================
select * from public.v_classification_stats_1d_overall;


-- =====================================================
-- 3. SAMPLE RECENT PREDICTIONS (SPY)
-- =====================================================
select 
    symbol,
    date,
    y_class_1d,
    rsi_14,
    macd_hist,
    vix_level,
    yield_curve_slope
from public.v_classification_dataset_1d
where symbol = 'SPY'
order by date desc
limit 20;


-- =====================================================
-- 4. FULL CLASSIFICATION DATASET (for model training)
-- =====================================================
-- 25,907 rows × 85 columns (83 features + symbol + date + y_class_1d)
select * from public.v_classification_dataset_1d
order by symbol, date;


-- =====================================================
-- 5. CHECK FOR NULLS IN TARGET
-- =====================================================
select 
    symbol,
    count(*) as total_rows,
    count(y_class_1d) as non_null_targets,
    count(*) - count(y_class_1d) as null_targets
from public.v_classification_dataset_1d
group by symbol;

-- Expected: Few nulls (only in 252-day warm-up period)


-- =====================================================
-- 6. CLASS DISTRIBUTION BY YEAR (trend analysis)
-- =====================================================
select 
    extract(year from date) as year,
    count(*) filter (where y_class_1d = 1) as count_buy,
    count(*) filter (where y_class_1d = 0) as count_hold,
    count(*) filter (where y_class_1d = -1) as count_sell,
    round(100.0 * count(*) filter (where y_class_1d = 1) / count(*), 2) as pct_buy,
    round(100.0 * count(*) filter (where y_class_1d = 0) / count(*), 2) as pct_hold,
    round(100.0 * count(*) filter (where y_class_1d = -1) / count(*), 2) as pct_sell
from public.v_classification_dataset_1d
where y_class_1d is not null
group by extract(year from date)
order by year desc;


-- =====================================================
-- 7. FEATURE CORRELATION WITH TARGET (QQQ example)
-- =====================================================
-- Get data for correlation analysis
select 
    y_class_1d,
    rsi_14,
    macd_hist,
    vix_level,
    vix_change_1d,
    yield_curve_slope,
    hy_oas_level,
    volume_z,
    log_ret_1d,
    log_ret_5d
from public.v_classification_dataset_1d
where symbol = 'QQQ'
    and y_class_1d is not null
order by date;


-- =====================================================
-- 8. RECENT BUY SIGNALS (all symbols)
-- =====================================================
select 
    symbol,
    date,
    rsi_14,
    macd_hist,
    vix_level,
    yield_curve_slope
from public.v_classification_dataset_1d
where y_class_1d = 1
    and date >= current_date - interval '30 days'
order by date desc, symbol;


-- =====================================================
-- 9. VALIDATION: RUN DATASET CHECKS
-- =====================================================
select * from public.validate_classification_dataset_1d();


-- =====================================================
-- 10. EXPORT FOR PYTHON MODELING
-- =====================================================
-- Copy this to CSV for pandas/sklearn
\copy (select * from public.v_classification_dataset_1d order by symbol, date) to 'classification_dataset.csv' with csv header;


-- =====================================================
-- 11. CHECK DATE RANGE COVERAGE
-- =====================================================
select 
    symbol,
    min(date) as first_date,
    max(date) as last_date,
    count(distinct date) as trading_days,
    count(*) filter (where y_class_1d is not null) as valid_targets
from public.v_classification_dataset_1d
group by symbol
order by symbol;


-- =====================================================
-- 12. FEATURE PREVIEW (column names and types)
-- =====================================================
select 
    column_name,
    data_type,
    is_nullable
from information_schema.columns
where table_schema = 'public'
    and table_name = 'v_classification_dataset_1d'
order by ordinal_position;
