-- Clear all data tables for fresh ETL run
-- This preserves table structure but removes all data

begin;

truncate table public.labels_daily cascade;
truncate table public.features_daily cascade;
truncate table public.daily_bars cascade;
truncate table public.corporate_actions cascade;
truncate table public.macro_daily cascade;
truncate table public.events_calendar cascade;

-- Keep metadata tables (assets, macro_series, feature_metadata)

commit;

select 'All data tables cleared - ready for fresh ETL run' as status;
