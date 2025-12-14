-- Migration: Add macro, events, and proxy assets for context features
-- All dates are ET (America/New_York) trading dates

begin;

-- Extend assets table to support macro, proxy, and event types
alter table public.assets
  add column if not exists timezone text default 'America/New_York';

comment on column public.assets.timezone is 'Timezone for data alignment, always America/New_York for US equities';

-- Add days_since_update tracking for sparse series (FRED weekly/monthly)
alter table public.macro_daily
  add column if not exists days_since_update int default 0;

comment on column public.macro_daily.days_since_update is 'Days since last actual observation (0 for observed, >0 for forward-filled)';

-- Add units and timezone to macro_series
alter table public.macro_series
  add column if not exists units text,
  add column if not exists timezone text default 'America/New_York';

comment on column public.macro_series.units is 'Units of measurement (percent, basis points, dollars, etc)';
comment on column public.macro_series.timezone is 'Timezone for data alignment';

-- Events calendar table
create table if not exists public.events_calendar (
  id uuid primary key default uuid_generate_v4(),
  date date not null,
  event_type text not null,
  event_name text,
  source text,
  created_at timestamptz not null default now(),
  unique(date, event_type)
);

comment on table public.events_calendar is 'Calendar events (month-end, FOMC, CPI, NFP, options expiry) aligned to ET trading days';
comment on column public.events_calendar.event_type is 'Type: month_end, quarter_end, options_expiry_week, fomc, cpi_release, nfp_release';

-- Indexes for fast event lookups
create index if not exists idx_events_calendar_date on public.events_calendar(date);
create index if not exists idx_events_calendar_type_date on public.events_calendar(event_type, date desc);

-- Enhanced model dataset view with context features
-- This view joins ETF bars + features + labels + macro context + events
create or replace view public.v_model_dataset_enhanced as
select 
  a.symbol,
  db.date,
  db.open, db.high, db.low, db.close, db.adj_close, db.volume,
  f.feature_json,
  l.y_1d, l.y_5d, l.y_thresh,
  -- Event flags as boolean columns
  exists(select 1 from public.events_calendar ec where ec.date = db.date and ec.event_type = 'month_end') as is_month_end,
  exists(select 1 from public.events_calendar ec where ec.date = db.date and ec.event_type = 'quarter_end') as is_quarter_end,
  exists(select 1 from public.events_calendar ec where ec.date = db.date and ec.event_type = 'options_expiry_week') as is_options_expiry_week,
  exists(select 1 from public.events_calendar ec where ec.date = db.date and ec.event_type = 'fomc') as is_fomc_day,
  exists(select 1 from public.events_calendar ec where ec.date = db.date and ec.event_type = 'cpi_release') as is_cpi_release_day,
  exists(select 1 from public.events_calendar ec where ec.date = db.date and ec.event_type = 'nfp_release') as is_nfp_release_day
from public.daily_bars db
join public.assets a on a.id = db.asset_id
left join public.features_daily f on f.asset_id = db.asset_id and f.date = db.date
left join public.labels_daily l on l.asset_id = db.asset_id and l.date = db.date
where a.asset_type = 'ETF';

comment on view public.v_model_dataset_enhanced is 'Enhanced modeling dataset with event flags for ETF classification';

commit;
