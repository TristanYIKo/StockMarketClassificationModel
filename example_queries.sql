-- Example modeling dataset query for SPY with context features
-- Run this after ETL completes to fetch training data

-- Option 1: Using the enhanced view with event flags
select 
  symbol, 
  date,
  open, high, low, close, adj_close, volume,
  -- Event flags (from view)
  is_month_end,
  is_quarter_end,
  is_options_expiry_week,
  is_fomc_day,
  is_cpi_release_day,
  is_nfp_release_day,
  -- Labels
  y_1d, 
  y_5d, 
  y_thresh
from public.v_model_dataset_enhanced
where symbol = 'SPY' 
  and date between '2015-01-01' and '2023-12-31'
order by date;

-- Option 2: Flatten specific features from JSON
select 
  symbol, 
  date,
  close,
  -- Technical features
  (feature_json->>'rsi_14')::numeric as rsi_14,
  (feature_json->>'macd_line')::numeric as macd_line,
  (feature_json->>'macd_signal')::numeric as macd_signal,
  (feature_json->>'vol_20')::numeric as vol_20,
  (feature_json->>'sma_20')::numeric as sma_20,
  (feature_json->>'sma_50')::numeric as sma_50,
  (feature_json->>'sma20_gt_sma50')::int as sma20_gt_sma50,
  (feature_json->>'atr_14')::numeric as atr_14,
  (feature_json->>'dd_20')::numeric as dd_20,
  -- Macro features
  (feature_json->>'DGS2')::numeric as dgs2,
  (feature_json->>'DGS10')::numeric as dgs10,
  (feature_json->>'yield_curve_slope')::numeric as yield_curve_slope,
  (feature_json->>'dgs10_change_1d')::numeric as dgs10_change_1d,
  (feature_json->>'hy_oas_level')::numeric as hy_oas_level,
  (feature_json->>'hy_oas_change_5d')::numeric as hy_oas_change_5d,
  (feature_json->>'liquidity_expanding')::int as liquidity_expanding,
  (feature_json->>'fed_balance_sheet_change_pct')::numeric as fed_bs_chg_pct,
  -- VIX features
  (feature_json->>'vix_level')::numeric as vix_level,
  (feature_json->>'vix_change_1d')::numeric as vix_change_1d,
  (feature_json->>'vix_change_5d')::numeric as vix_change_5d,
  (feature_json->>'vix_term_structure')::numeric as vix_term_structure,
  -- Cross-asset features
  (feature_json->>'dxy_ret_5d')::numeric as dxy_ret_5d,
  (feature_json->>'gold_ret_5d')::numeric as gold_ret_5d,
  (feature_json->>'oil_ret_5d')::numeric as oil_ret_5d,
  (feature_json->>'hyg_ret_5d')::numeric as hyg_ret_5d,
  (feature_json->>'hyg_vs_spy_5d')::numeric as hyg_vs_spy_5d,
  (feature_json->>'hyg_spy_corr_20d')::numeric as hyg_spy_corr_20d,
  (feature_json->>'tlt_ret_5d')::numeric as tlt_ret_5d,
  -- Breadth features
  (feature_json->>'rsp_spy_ratio')::numeric as rsp_spy_ratio,
  (feature_json->>'rsp_spy_ratio_z')::numeric as rsp_spy_ratio_z,
  (feature_json->>'qqq_spy_ratio_z')::numeric as qqq_spy_ratio_z,
  (feature_json->>'iwm_spy_ratio_z')::numeric as iwm_spy_ratio_z,
  -- Event flags
  (feature_json->>'is_month_end')::int as is_month_end,
  (feature_json->>'is_quarter_end')::int as is_quarter_end,
  (feature_json->>'is_options_expiry_week')::int as is_options_expiry_week,
  (feature_json->>'is_fomc')::int as is_fomc,
  (feature_json->>'is_cpi_release')::int as is_cpi_release,
  (feature_json->>'is_nfp_release')::int as is_nfp_release,
  -- Labels
  y_1d, 
  y_5d, 
  y_thresh
from public.v_model_dataset
where symbol = 'SPY' 
  and date between '2015-01-01' and '2023-12-31'
order by date;

-- Option 3: Check data coverage
select 
  a.symbol,
  count(distinct db.date) as bar_days,
  count(distinct f.date) as feature_days,
  count(distinct l.date) as label_days,
  min(db.date) as first_date,
  max(db.date) as last_date
from public.assets a
left join public.daily_bars db on db.asset_id = a.id
left join public.features_daily f on f.asset_id = a.id
left join public.labels_daily l on l.asset_id = a.id
where a.symbol in ('SPY', 'QQQ', 'DIA', 'IWM')
group by a.symbol
order by a.symbol;

-- Option 4: Check macro data coverage
select 
  ms.series_key,
  ms.name,
  count(md.id) as observations,
  min(md.date) as first_date,
  max(md.date) as last_date,
  avg(md.days_since_update) as avg_days_since_update
from public.macro_series ms
left join public.macro_daily md on md.series_id = ms.id
group by ms.series_key, ms.name
order by ms.series_key;

-- Option 5: Check events coverage
select 
  event_type,
  count(*) as event_count,
  min(date) as first_event,
  max(date) as last_event
from public.events_calendar
group by event_type
order by event_type;
