-- Migration: Add outcome price columns for forward-looking predictions
-- Date: 2025-12-22 
--
-- OBJECTIVE: Store actual future prices separately from computed labels
-- This allows us to:
-- 1. Insert rows for today even when we don't have tomorrow's data yet
-- 2. Backfill outcome prices as new data arrives
-- 3. Make predictions before the outcome is known

begin;

-- Add outcome price columns to daily_bars
alter table public.daily_bars
  add column if not exists outcome_price_1d numeric,
  add column if not exists outcome_price_5d numeric;

comment on column public.daily_bars.outcome_price_1d is 
  'Close price 1 trading day in the future (for next-day predictions). NULL if not yet available.';

comment on column public.daily_bars.outcome_price_5d is 
  'Close price 5 trading days in the future (for weekly predictions). NULL if not yet available.';

-- Add index for efficient outcome price queries
create index if not exists idx_daily_bars_outcomes
  on public.daily_bars(asset_id, date)
  where outcome_price_1d is not null or outcome_price_5d is not null;

commit;
