-- Helper functions for data validation

-- Check for duplicate (asset_id, date) in features_daily
create or replace function public.check_duplicates_features()
returns table(count bigint) as $$
  select count(*) 
  from (
    select asset_id, date
    from public.features_daily
    group by asset_id, date
    having count(*) > 1
  ) as dupes;
$$ language sql;

-- Check for duplicate (asset_id, date) in labels_daily
create or replace function public.check_duplicates_labels()
returns table(count bigint) as $$
  select count(*) 
  from (
    select asset_id, date
    from public.labels_daily
    group by asset_id, date
    having count(*) > 1
  ) as dupes;
$$ language sql;

-- Get feature NaN counts for a specific asset and date range
create or replace function public.get_nan_summary(
  p_symbol text,
  p_start_date date,
  p_end_date date
)
returns table(
  feature text,
  nan_count bigint,
  total_rows bigint,
  nan_pct numeric
) as $$
  select 
    'sma_200' as feature,
    sum(case when (feature_json->>'sma_200') is null then 1 else 0 end) as nan_count,
    count(*) as total_rows,
    round(100.0 * sum(case when (feature_json->>'sma_200') is null then 1 else 0 end) / count(*), 2) as nan_pct
  from public.features_daily fd
  join public.assets a on a.id = fd.asset_id
  where a.symbol = p_symbol
    and fd.date between p_start_date and p_end_date
  
  union all
  
  select 
    'vol_60',
    sum(case when (feature_json->>'vol_60') is null then 1 else 0 end),
    count(*),
    round(100.0 * sum(case when (feature_json->>'vol_60') is null then 1 else 0 end) / count(*), 2)
  from public.features_daily fd
  join public.assets a on a.id = fd.asset_id
  where a.symbol = p_symbol
    and fd.date between p_start_date and p_end_date;
$$ language sql;
