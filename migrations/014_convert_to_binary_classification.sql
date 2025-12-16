-- Migration: Convert to binary classification (UP/DOWN only)
-- Date: 2025-12-15
--
-- Removes HOLD class, converts to binary UP (1) / DOWN (-1)

begin;

-- 1. Drop the existing table
drop table if exists public.model_predictions_classification cascade;

-- 2. Recreate with binary structure
create table public.model_predictions_classification (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  date date not null,
  horizon text not null,         -- '1d' or '5d'
  model_name text not null,
  split text not null,           -- 'val' | 'test' | 'live'
  y_true int,                    -- null for live predictions: 1 (UP) or -1 (DOWN)
  pred_class_raw int not null,   -- 1 (UP) or -1 (DOWN)
  pred_class_final int not null, -- 1 (UP) or -1 (DOWN)
  p_down numeric not null,       -- Probability of DOWN movement
  p_up numeric not null,         -- Probability of UP movement
  confidence numeric not null,   -- max(p_down, p_up)
  margin numeric not null,       -- abs(p_up - p_down)
  created_at timestamptz default now(),
  unique(symbol, date, horizon, model_name, split)
);

comment on table public.model_predictions_classification is 
  'Binary classification predictions: UP vs DOWN movements';

comment on column public.model_predictions_classification.horizon is 
  'Prediction horizon: 1d (next day) or 5d (weekly)';

comment on column public.model_predictions_classification.pred_class_raw is 
  'Raw prediction: 1 (UP), -1 (DOWN)';

comment on column public.model_predictions_classification.pred_class_final is 
  'Final prediction after confidence gating: 1 (UP), -1 (DOWN)';

comment on column public.model_predictions_classification.p_down is 
  'Probability of downward movement';

comment on column public.model_predictions_classification.p_up is 
  'Probability of upward movement';

comment on column public.model_predictions_classification.confidence is 
  'Maximum probability between UP and DOWN';

comment on column public.model_predictions_classification.margin is 
  'Absolute difference between p_up and p_down (prediction strength)';

-- Indexes for efficient querying
create index idx_model_preds_symbol_date 
  on public.model_predictions_classification(symbol, date desc);

create index idx_model_preds_horizon_model 
  on public.model_predictions_classification(horizon, model_name, split);

commit;
