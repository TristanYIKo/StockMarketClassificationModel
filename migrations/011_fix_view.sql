-- Quick fix for integer casting issue in classification views
-- Run this in Supabase SQL Editor

-- Step 1: Drop existing views
drop view if exists public.v_classification_dataset_1d cascade;
drop view if exists public.v_classification_stats_1d cascade;
drop view if exists public.v_classification_stats_1d_overall cascade;
drop function if exists public.validate_classification_dataset_1d() cascade;

-- Step 2: Now run the entire migrations/008_add_classification_support.sql file
-- (copy and paste the full content into SQL Editor after running this)

select 'Views dropped - now run migrations/008_add_classification_support.sql' as status;
