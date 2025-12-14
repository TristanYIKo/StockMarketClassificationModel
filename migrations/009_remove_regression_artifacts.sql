-- Migration: Remove regression-specific views and artifacts
-- Date: 2025-12-14
-- Purpose: Streamline database for classification-only workflow

begin;

-- =========================================
-- A) DROP REGRESSION-SPECIFIC VIEWS
-- =========================================

drop view if exists public.v_regression_dataset_optimized cascade;
drop view if exists public.v_regression_diagnostics cascade;
drop view if exists public.v_optimization_summary cascade;

-- =========================================
-- B) DROP REGRESSION-SPECIFIC METADATA TABLES
-- =========================================

drop table if exists public.feature_exclusions cascade;
drop function if exists public.validate_regression_dataset() cascade;

-- =========================================
-- C) UPDATE LABELS TABLE COMMENTS (mark what's active vs deprecated)
-- =========================================

comment on column public.labels_daily.y_class_1d is 
  'PRIMARY TARGET: Classification target (-1=Sell, 0=Hold, 1=Buy) using triple-barrier method';

comment on column public.labels_daily.y_1d_vol is 
  'INTERNAL: Volatility-scaled return used to compute y_class_1d';

-- Mark old columns as deprecated but keep for diagnostics
comment on column public.labels_daily.y_1d_vol_clip is 
  'DEPRECATED: Was regression target, kept for diagnostics';
comment on column public.labels_daily.y_5d_vol_clip is 
  'DEPRECATED: Was regression target, kept for diagnostics';
comment on column public.labels_daily.primary_target is 
  'DEPRECATED: Was regression target alias, kept for diagnostics';
comment on column public.labels_daily.y_1d is 
  'DEPRECATED: Legacy binary target, kept for diagnostics';
comment on column public.labels_daily.y_5d is 
  'DEPRECATED: Legacy 5-day target, kept for diagnostics';
comment on column public.labels_daily.y_thresh is 
  'DEPRECATED: Legacy threshold target, kept for diagnostics';
comment on column public.labels_daily.y_1d_raw is 
  'DEPRECATED: Raw returns, kept for diagnostics';
comment on column public.labels_daily.y_5d_raw is 
  'DEPRECATED: 5-day returns, kept for diagnostics';
comment on column public.labels_daily.y_5d_vol is 
  'DEPRECATED: 5-day vol-scaled returns, kept for diagnostics';
comment on column public.labels_daily.y_1d_clipped is 
  'DEPRECATED: Clipped returns, kept for diagnostics';
comment on column public.labels_daily.y_5d_clipped is 
  'DEPRECATED: Clipped 5-day returns, kept for diagnostics';

-- =========================================
-- D) UPDATE FEATURE METADATA TABLE COMMENT
-- =========================================

comment on table public.feature_metadata is 
  'Feature registry for classification model - 83 features used for trading signal prediction';

commit;

-- =========================================
-- VALIDATION
-- =========================================

select 'Migration 009 Complete' as status,
       'Dropped regression views and feature_exclusions table' as action,
       'Classification-only infrastructure ready' as result;
