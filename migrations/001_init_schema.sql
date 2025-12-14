-- Migration: Initial schema for ETF classification data layer
-- Store everything in UTC; dates are US market trading days

begin;

create extension if not exists "uuid-ossp";

-- Assets
create table if not exists public.assets (
  id uuid primary key default uuid_generate_v4(),
  symbol text not null unique,
  name text,
  asset_type text,
  exchange text,
  currency text default 'USD'
);

-- Daily OHLCV bars
create table if not exists public.daily_bars (
  id uuid primary key default uuid_generate_v4(),
  asset_id uuid not null references public.assets(id) on delete cascade,
  date date not null,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  adj_close numeric,
  volume bigint,
  source text default 'yfinance',
  created_at timestamptz not null default now(),
  unique(asset_id, date)
);

-- Corporate actions
create table if not exists public.corporate_actions (
  id uuid primary key default uuid_generate_v4(),
  asset_id uuid not null references public.assets(id) on delete cascade,
  date date not null,
  dividend numeric,
  split_ratio numeric,
  source text default 'yfinance',
  unique(asset_id, date)
);

-- Macro series catalog
create table if not exists public.macro_series (
  id uuid primary key default uuid_generate_v4(),
  series_key text not null unique,
  name text,
  frequency text default 'daily',
  source text
);

-- Macro daily values
create table if not exists public.macro_daily (
  id uuid primary key default uuid_generate_v4(),
  series_id uuid not null references public.macro_series(id) on delete cascade,
  date date not null,
  value numeric,
  unique(series_id, date)
);

-- Features JSON per day (optional; can be flattened later)
create table if not exists public.features_daily (
  id uuid primary key default uuid_generate_v4(),
  asset_id uuid not null references public.assets(id) on delete cascade,
  date date not null,
  feature_json jsonb not null,
  created_at timestamptz not null default now(),
  unique(asset_id, date)
);

-- Labels per day
create table if not exists public.labels_daily (
  id uuid primary key default uuid_generate_v4(),
  asset_id uuid not null references public.assets(id) on delete cascade,
  date date not null,
  y_1d int,
  y_5d int,
  y_thresh int,
  created_at timestamptz not null default now(),
  unique(asset_id, date)
);

-- Helpful indexes
create index if not exists idx_daily_bars_asset_date_desc on public.daily_bars(asset_id, date desc);
create index if not exists idx_features_daily_asset_date_desc on public.features_daily(asset_id, date desc);
create index if not exists idx_labels_daily_asset_date_desc on public.labels_daily(asset_id, date desc);
create index if not exists idx_macro_daily_series_date_desc on public.macro_daily(series_id, date desc);

-- Modeling dataset view: assets + daily_bars + features + labels
-- Flatten features from jsonb using ->> when needed; here we expose jsonb
create or replace view public.v_model_dataset as
select 
  a.symbol,
  db.date,
  db.open, db.high, db.low, db.close, db.adj_close, db.volume,
  f.feature_json,
  l.y_1d, l.y_5d, l.y_thresh
from public.daily_bars db
join public.assets a on a.id = db.asset_id
left join public.features_daily f on f.asset_id = db.asset_id and f.date = db.date
left join public.labels_daily l on l.asset_id = db.asset_id and l.date = db.date;

commit;
