-- Migration: Add 5-day classification support
-- Date: 2025-12-14
--
-- Add y_class_5d for weekly (5 trading day) classification

begin;

-- Add 5-day classification target column
alter table public.labels_daily
  add column if not exists y_class_5d int;

comment on column public.labels_daily.y_class_5d is 
  'Triple-barrier classification target (5-day): 1 (Buy), 0 (Hold), -1 (Sell) based on y_5d_vol thresholds (±0.25)';

-- Compute y_class_5d using volatility-scaled 5-day returns
update public.labels_daily
set y_class_5d = case
  when y_5d_vol is null then null
  when y_5d_vol > 0.25 then 1   -- Significant up move (Buy)
  when y_5d_vol < -0.25 then -1  -- Significant down move (Sell)
  else 0                         -- Noise/chop range (Hold)
end;

-- Add index for 5-day classification queries
create index if not exists idx_labels_daily_y_class_5d 
  on public.labels_daily(asset_id, date) 
  where y_class_5d is not null;

commit;
