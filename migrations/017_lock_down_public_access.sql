-- Migration 017: row-level security -- make the public key read-only
--
-- BACKGROUND
-- Until now every table was reachable with the anon key, and that key was
-- embedded in the website's JavaScript bundle. Anyone who opened the site could
-- read it out of a chunk and then INSERT, UPDATE or DELETE any row in
-- daily_bars, predictions or labels_daily.
--
-- The anon key is *designed* to be public in Supabase; what makes it dangerous
-- is the absence of RLS. This migration enables RLS everywhere and grants the
-- public roles SELECT only. The service_role key bypasses RLS entirely, which
-- is how the ETL keeps writing.
--
-- ORDER OF OPERATIONS -- READ BEFORE RUNNING
--   1. Copy the service_role key from Supabase -> Settings -> API.
--   2. Add it as SUPABASE_SERVICE_KEY: a GitHub Actions secret, and in your
--      local .env.
--   3. Run THIS migration.
--   4. Rotate the anon key (Settings -> API -> roll). The old one has been
--      public and must be treated as compromised. Update web/.env.local and the
--      hosting provider's env vars with the new value.
--
-- Running this before step 2 will not lose data, but the daily pipeline's
-- writes will start being rejected.

begin;

-- Read-only for the public roles, on every table the dashboard touches.
do $$
declare
  t text;
begin
  foreach t in array array[
    'assets', 'daily_bars', 'features_daily', 'labels_daily',
    'macro_series', 'macro_daily', 'events_calendar',
    'corporate_actions', 'predictions'
  ]
  loop
    if to_regclass('public.' || t) is null then
      raise notice 'skipping %: table does not exist', t;
      continue;
    end if;

    execute format('alter table public.%I enable row level security', t);

    -- Drop first so re-running the migration is safe.
    execute format('drop policy if exists %I on public.%I', t || '_public_read', t);
    execute format(
      'create policy %I on public.%I for select to anon, authenticated using (true)',
      t || '_public_read', t);

    -- No INSERT/UPDATE/DELETE policy is created. With RLS on and no permissive
    -- policy for those commands, they are denied for anon and authenticated.
    -- service_role bypasses RLS and is unaffected.
    raise notice 'locked down %', t;
  end loop;
end $$;

commit;

-- Verify: every table should report rowsecurity = true and exactly one
-- SELECT policy.
--
--   select c.relname, c.relrowsecurity, p.polname, p.polcmd
--   from pg_class c
--   left join pg_policy p on p.polrelid = c.oid
--   join pg_namespace n on n.oid = c.relnamespace
--   where n.nspname = 'public' and c.relkind = 'r'
--   order by c.relname;
