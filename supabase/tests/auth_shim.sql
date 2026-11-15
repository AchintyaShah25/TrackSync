-- Test-only stand-in for the parts of Supabase's `auth` schema our migrations use.
-- Fresh test databases (conftest.fresh_database) are plain `create database` copies that lack
-- the auth schema GoTrue creates in the real `postgres` database. Definitions mirror Supabase:
-- auth.uid() reads the `sub` claim from request.jwt.claims (set per transaction by the API).

create schema if not exists auth;
-- Supabase installs extensions (pgvector) into this schema.
create schema if not exists extensions;

create table if not exists auth.users (
  id uuid primary key
);

create or replace function auth.uid() returns uuid
  language sql stable
as $$
  select
  coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;

grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
