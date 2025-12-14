-- Migration: Add human-readable descriptive columns
-- Makes database tables easier to understand without constantly joining IDs
-- Date: 2025-12-13

begin;

-- =========================================
-- A) ADD DESCRIPTIONS TO ASSETS TABLE
-- =========================================

-- Add description column to assets
alter table public.assets
  add column if not exists description text;

-- Update with readable descriptions
update public.assets set description = 'S&P 500 ETF' where symbol = 'SPY';
update public.assets set description = 'Nasdaq-100 ETF' where symbol = 'QQQ';
update public.assets set description = 'Dow Jones ETF' where symbol = 'DIA';
update public.assets set description = 'Russell 2000 Small-Cap ETF' where symbol = 'IWM';

comment on column public.assets.description is 'Human-readable description of the asset';

-- =========================================
-- B) ADD METADATA TO EXISTING MACRO_SERIES TABLE
-- =========================================

-- Add description and units columns to existing macro_series table
alter table public.macro_series
  add column if not exists description text,
  add column if not exists units text;

comment on column public.macro_series.description is 
  'Detailed description of the macro/economic time series';
comment on column public.macro_series.units is 
  'Units of measurement (e.g., Percent, Basis Points, Millions of Dollars)';

-- Update existing series with descriptions
update public.macro_series set 
  description = 'Market Yield on U.S. Treasury Securities at 2-Year Constant Maturity',
  units = 'Percent'
where series_key = 'DGS2';

update public.macro_series set 
  description = 'Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity',
  units = 'Percent'
where series_key = 'DGS10';

update public.macro_series set 
  description = 'Effective Federal Funds Rate (Target Rate)',
  units = 'Percent'
where series_key = 'FEDFUNDS';

update public.macro_series set 
  description = 'Effective Federal Funds Rate (Actual Traded Rate)',
  units = 'Percent'
where series_key = 'EFFR';

update public.macro_series set 
  description = '10-Year Breakeven Inflation Rate (TIPS-based)',
  units = 'Percent'
where series_key = 'T10YIE';

update public.macro_series set 
  description = 'ICE BofA US High Yield Option-Adjusted Spread',
  units = 'Basis Points'
where series_key = 'BAMLH0A0HYM2';

update public.macro_series set 
  description = 'Federal Reserve Total Assets (Balance Sheet Size)',
  units = 'Millions of Dollars'
where series_key = 'WALCL';

update public.macro_series set 
  description = 'Overnight Reverse Repurchase Agreements (Fed Facility)',
  units = 'Billions of Dollars'
where series_key = 'RRPONTSYD';

update public.macro_series set 
  description = 'Secured Overnight Financing Rate',
  units = 'Percent'
where series_key = 'SOFR';

-- =========================================
-- C) CREATE EVENT TYPE LOOKUP TABLE
-- =========================================

create table if not exists public.event_type_metadata (
  event_type text primary key,
  name text not null,
  description text not null,
  typical_impact text,
  frequency_per_year int
);

comment on table public.event_type_metadata is 
  'Metadata and descriptions for economic event types';

-- Insert event type descriptions
insert into public.event_type_metadata (event_type, name, description, typical_impact, frequency_per_year) values
  ('fomc', 'FOMC Meeting', 'Federal Open Market Committee monetary policy decision', 'High volatility, rates-sensitive sectors react', 8),
  ('cpi_release', 'CPI Release', 'Consumer Price Index (inflation data) release', 'Market-moving inflation data, affects Fed policy expectations', 12),
  ('nfp_release', 'Jobs Report', 'Non-Farm Payrolls employment data release', 'Major market mover, first Friday of month', 12)
on conflict (event_type) do update set
  name = excluded.name,
  description = excluded.description,
  typical_impact = excluded.typical_impact,
  frequency_per_year = excluded.frequency_per_year;

-- =========================================
-- D) SKIP ADDING COLUMNS (Use Views Instead)
-- =========================================

-- Note: PostgreSQL doesn't allow subqueries in generated columns
-- Instead, we'll use views with joins to show human-readable data

-- =========================================
-- G) CREATE HELPER VIEWS FOR BROWSING DATA
-- =========================================

-- Drop existing views if they exist (allows changing column structure)
drop view if exists public.v_daily_bars_readable cascade;
drop view if exists public.v_features_daily_readable cascade;
drop view if exists public.v_labels_daily_readable cascade;

-- View for browsing daily bars with full context
create view public.v_daily_bars_readable as
select 
  a.symbol,
  a.description as asset_description,
  a.asset_type,
  db.date,
  to_char(db.date, 'Day') as day_of_week,
  db.open,
  db.high,
  db.low,
  db.close,
  db.adj_close,
  db.volume,
  round(((db.close - db.open) / db.open * 100)::numeric, 2) as intraday_pct,
  round((db.volume / 1000000.0)::numeric, 2) as volume_millions
from public.daily_bars db
join public.assets a on a.id = db.asset_id
order by db.date desc, a.symbol;

comment on view public.v_daily_bars_readable is 
  'Daily bars with human-readable asset info and computed metrics';

-- View for browsing features with ETF symbol
create view public.v_features_daily_readable as
select 
  a.symbol,
  a.description as asset_description,
  f.date,
  f.feature_json,
  f.created_at
from public.features_daily f
join public.assets a on a.id = f.asset_id
order by f.date desc, a.symbol;

comment on view public.v_features_daily_readable is 
  'Features with ETF symbol and name for easy browsing';

-- View for browsing labels with ETF symbol
create view public.v_labels_daily_readable as
select 
  a.symbol,
  a.description as asset_description,
  l.date,
  -- Regression targets
  l.y_1d_raw,
  l.y_5d_raw,
  l.y_1d_vol,
  l.y_5d_vol,
  l.y_1d_clipped,
  l.y_5d_clipped,
  -- Classification targets
  l.y_1d,
  l.y_5d,
  l.y_thresh
from public.labels_daily l
join public.assets a on a.id = l.asset_id
order by l.date desc, a.symbol;

comment on view public.v_labels_daily_readable is 
  'Labels/targets with ETF symbol and name for easy browsing';

-- View for browsing macro data with descriptions
create or replace view public.v_macro_daily_readable as
select 
  m.date,
  ms.series_key as code,
  ms.name,
  ms.description,
  m.value,
  ms.units
from public.macro_daily m
left join public.macro_series ms on ms.id = m.series_id
order by m.date desc, ms.name;

comment on view public.v_macro_daily_readable is 
  'Macro series with full metadata and descriptions';

-- View for browsing events with descriptions
create or replace view public.v_events_readable as
select 
  e.date,
  to_char(e.date, 'Day, Mon DD, YYYY') as date_formatted,
  e.event_type as code,
  et.name as event_name,
  et.description,
  et.typical_impact
from public.events_calendar e
left join public.event_type_metadata et on et.event_type = e.event_type
order by e.date desc;

comment on view public.v_events_readable is 
  'Events calendar with full descriptions and impact notes';

-- =========================================
-- H) ADD COLUMN COMMENTS TO KEY TABLES
-- =========================================

-- Add comments to labels_daily columns
comment on column public.labels_daily.y_1d is 'Next day simple return: (close[t+1] - close[t]) / close[t]';
comment on column public.labels_daily.y_5d is '5-day forward return: (close[t+5] - close[t]) / close[t]';
comment on column public.labels_daily.y_thresh is 'Binary classification: 1 if next day return > threshold';
comment on column public.labels_daily.y_1d_raw is '1-day forward log return (raw, unscaled)';
comment on column public.labels_daily.y_5d_raw is '5-day forward log return (raw, unscaled)';
comment on column public.labels_daily.y_1d_vol is '1-day return / rolling_vol_20 (volatility-scaled, better for regression)';
comment on column public.labels_daily.y_5d_vol is '5-day return / rolling_vol_20 (volatility-scaled, better for regression)';
comment on column public.labels_daily.y_1d_clipped is '1-day return clipped to ±3 standard deviations (outlier robust)';
comment on column public.labels_daily.y_5d_clipped is '5-day return clipped to ±3 standard deviations (outlier robust)';

-- Add comments to daily_bars columns
comment on column public.daily_bars.open is 'Opening price at 9:30 AM ET';
comment on column public.daily_bars.high is 'Highest price during trading day';
comment on column public.daily_bars.low is 'Lowest price during trading day';
comment on column public.daily_bars.close is 'Closing price at 4:00 PM ET (unadjusted)';
comment on column public.daily_bars.adj_close is 'Adjusted closing price (accounts for splits and dividends)';
comment on column public.daily_bars.volume is 'Total shares traded during the day';

commit;
