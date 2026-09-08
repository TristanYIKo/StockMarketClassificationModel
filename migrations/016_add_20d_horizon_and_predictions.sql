-- Migration 016: 20-day horizon + a predictions table with unambiguous dates
--
-- Two things:
--   1. Add the 20d horizon alongside the existing 1d and 5d columns.
--   2. Replace model_predictions_classification with `predictions`, which
--      separates as_of_date (the day whose close the features describe) from
--      target_date (the day being predicted).
--
--      The old table had a single `date` whose meaning varied by writer:
--      training wrote the feature date, production wrote the target date. The
--      website read both from the same query and evaluated every row as if
--      `date` were the feature date, so every production row was scored against
--      the wrong day's return. Splitting the columns removes the ambiguity.

begin;

-- ---------------------------------------------------------------- 20d labels
alter table public.labels_daily
  add column if not exists y_class_20d   int,
  add column if not exists y_20d_raw     numeric,
  add column if not exists y_20d_vol     numeric,
  add column if not exists y_20d_clipped numeric,
  add column if not exists y_20d_vol_clip numeric;

comment on column public.labels_daily.y_class_20d is
  'Binary target 20 trading days ahead: 1 (UP), -1 (DOWN). NULL until the future close exists.';

alter table public.daily_bars
  add column if not exists outcome_price_20d numeric;

comment on column public.daily_bars.outcome_price_20d is
  'Close price 20 trading days in the future. NULL until available. NOT a model feature.';

-- ------------------------------------------------------------- predictions
create table if not exists public.predictions (
  id            uuid primary key default gen_random_uuid(),
  symbol        text not null,
  horizon       text not null,                    -- '1d' | '5d' | '20d'

  -- The two dates that were previously conflated into one.
  as_of_date    date not null,                    -- features describe this day's close
  target_date   date not null,                    -- this day's close is being predicted

  model_name    text not null,
  split         text not null default 'production',  -- 'production' | 'val' | 'test' | 'backtest'

  pred_class    int  not null,                    -- 1 (UP) | -1 (DOWN)
  p_up          numeric not null,
  p_down        numeric not null,
  confidence    numeric not null,                 -- max(p_up, p_down)
  margin        numeric not null,                 -- abs(p_up - p_down)

  -- Denormalised so the site can render history in one query.
  as_of_close   numeric,
  outcome_close numeric,                          -- NULL until target_date closes
  actual_return numeric,                          -- ln(outcome_close / as_of_close)
  y_true        int,                              -- 1 | -1, NULL until resolved
  is_correct    boolean generated always as (
                  case when y_true is null then null else (pred_class = y_true) end
                ) stored,

  resolved_at   timestamptz,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now(),

  constraint predictions_horizon_chk   check (horizon in ('1d','5d','20d')),
  constraint predictions_class_chk     check (pred_class in (-1,1)),
  constraint predictions_ytrue_chk     check (y_true is null or y_true in (-1,1)),
  constraint predictions_order_chk     check (target_date > as_of_date),
  unique (symbol, horizon, as_of_date, model_name, split)
);

comment on table public.predictions is
  'Model predictions keyed by (as_of_date, target_date) so evaluation is unambiguous.';
comment on column public.predictions.as_of_date is
  'Trading day whose close the input features describe. The prediction is made after this close.';
comment on column public.predictions.target_date is
  'Trading day being predicted: as_of_date advanced by `horizon` NYSE trading days.';

create index if not exists idx_predictions_symbol_asof
  on public.predictions (symbol, horizon, as_of_date desc);
create index if not exists idx_predictions_unresolved
  on public.predictions (target_date)
  where y_true is null;
create index if not exists idx_predictions_split
  on public.predictions (split, model_name, horizon);

-- ------------------------------------------------------- accuracy roll-up
create or replace view public.v_prediction_accuracy as
select
  symbol,
  horizon,
  model_name,
  split,
  count(*)                                            as total,
  count(*) filter (where y_true is not null)          as resolved,
  count(*) filter (where is_correct)                  as hits,
  round(avg((is_correct)::int)::numeric, 4)           as accuracy,
  round(avg(confidence)::numeric, 4)                  as avg_confidence,
  max(as_of_date)                                     as latest_as_of
from public.predictions
group by symbol, horizon, model_name, split;

comment on view public.v_prediction_accuracy is
  'Hit rate per symbol/horizon/model over resolved predictions only.';

commit;
