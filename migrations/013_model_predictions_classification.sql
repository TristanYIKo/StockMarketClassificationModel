-- Migration: Create model_predictions_classification table
-- Date: 2025-12-14
--
-- Stores predictions for multiple horizons (1d, 5d) and models

begin;

create table if not exists public.model_predictions_classification (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  date date not null,
  horizon text not null,         -- '1d' or '5d'
  model_name text not null,
  split text not null,           -- 'val' | 'test' | 'live'
  y_true int,                    -- null for live predictions
  pred_class_raw int not null,
  pred_class_final int not null,
  p_sell numeric not null,
  p_hold numeric not null,
  p_buy numeric not null,
  confidence numeric not null,
  margin numeric not null,
  created_at timestamptz default now(),
  unique(symbol, date, horizon, model_name, split)
);

comment on table public.model_predictions_classification is 
  'Stores calibrated predictions for multi-horizon classification models';

comment on column public.model_predictions_classification.horizon is 
  'Prediction horizon: 1d (next day) or 5d (weekly)';

comment on column public.model_predictions_classification.pred_class_raw is 
  'Raw prediction before gating: -1 (Sell), 0 (Hold), 1 (Buy)';

comment on column public.model_predictions_classification.pred_class_final is 
  'Final prediction after confidence gating: -1 (Sell), 0 (Hold), 1 (Buy)';

comment on column public.model_predictions_classification.confidence is 
  'Maximum probability across all classes';

comment on column public.model_predictions_classification.margin is 
  'Difference between top two probabilities';

-- Indexes for efficient querying
create index if not exists idx_model_preds_symbol_date 
  on public.model_predictions_classification(symbol, date desc);

create index if not exists idx_model_preds_horizon_model 
  on public.model_predictions_classification(horizon, model_name, split);

create index if not exists idx_model_preds_date_horizon 
  on public.model_predictions_classification(date desc, horizon);

commit;
