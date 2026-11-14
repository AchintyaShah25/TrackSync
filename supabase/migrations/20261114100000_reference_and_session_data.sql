-- Milestone 1: reference data, session data, standings snapshots, ETL run log.
-- Keys are deterministic natural keys so ETL upserts are idempotent (docs/decisions/0005).
-- Session codes: R = race, S = sprint, Q = qualifying, SQ = sprint qualifying/shootout.

-- ---------------------------------------------------------------- reference data

create table public.seasons (
  year smallint primary key check (year >= 1950)
);

create table public.circuits (
  id            text primary key,              -- Jolpica circuitId, e.g. 'monza'
  name          text not null,
  locality      text,
  country       text,
  length_m      integer check (length_m > 0),
  rotation_deg  real,                          -- FastF1 CircuitInfo.rotation
  outline       jsonb,                         -- {"x":[...],"y":[...]} normalized, ~400 pts
  corners       jsonb,                         -- [{"number":1,"letter":"","x":..,"y":..,"angle":..}]
  outline_event_id integer,                    -- event whose pole lap produced the outline (newest wins)
  updated_at    timestamptz not null default now()
);

create table public.events (
  id              integer primary key,          -- season * 100 + round, e.g. 202416
  season          smallint not null references public.seasons (year),
  round           smallint not null check (round between 1 and 99),
  circuit_id      text not null references public.circuits (id),
  name            text not null,                -- 'Italian Grand Prix'
  slug            text not null,                -- 'italian-grand-prix'
  format          text not null,                -- FastF1 EventFormat: conventional, sprint_qualifying, ...
  race_start_utc  timestamptz,
  sessions        jsonb not null default '[]',  -- [{"code":"Q","name":"Qualifying","start_utc":"..."}]
  updated_at      timestamptz not null default now(),
  unique (season, round),
  check (id = season * 100 + round)
);
create index events_season_idx on public.events (season);

create table public.drivers (
  id          text primary key,                 -- Jolpica driverId, e.g. 'max_verstappen'
  code        text not null,                    -- 'VER'
  full_name   text not null,
  number      smallint
);

create table public.teams (
  id          text not null,                    -- Jolpica constructorId, e.g. 'red_bull'
  season      smallint not null references public.seasons (year),
  name        text not null,
  color_hex   text check (color_hex ~ '^#[0-9a-fA-F]{6}$'),
  primary key (id, season)
);

create table public.driver_teams (
  driver_id   text not null references public.drivers (id),
  team_id     text not null,
  season      smallint not null,
  primary key (driver_id, season, team_id),
  foreign key (team_id, season) references public.teams (id, season)
);

-- ---------------------------------------------------------------- session data

create table public.results (
  event_id    integer not null references public.events (id) on delete cascade,
  session     text not null check (session in ('R', 'S', 'Q', 'SQ')),
  driver_id   text not null references public.drivers (id),
  team_id     text not null,
  position    smallint,                         -- null when not classified
  grid        smallint,
  points      real not null default 0,
  status      text,                             -- 'Finished', '+1 Lap', 'Retired', ...
  time_ms     integer,                          -- race: total time; quali: best lap
  primary key (event_id, session, driver_id)
);

create table public.laps (
  event_id      integer not null references public.events (id) on delete cascade,
  session       text not null check (session in ('R', 'S')),
  driver_id     text not null references public.drivers (id),
  lap           smallint not null check (lap >= 1),
  lap_time_ms   integer,
  compound      text,                           -- SOFT, MEDIUM, HARD, INTERMEDIATE, WET
  tyre_life     smallint,
  stint         smallint,
  position      smallint,
  pit_in        boolean not null default false,
  pit_out       boolean not null default false,
  track_status  text,                           -- FastF1 status codes seen on the lap, e.g. '1', '24'
  is_accurate   boolean not null default false,
  deleted       boolean not null default false, -- lap time deleted (track limits)
  primary key (event_id, session, driver_id, lap)
);

create table public.stints (
  event_id    integer not null references public.events (id) on delete cascade,
  session     text not null check (session in ('R', 'S')),
  driver_id   text not null references public.drivers (id),
  stint       smallint not null check (stint >= 1),
  compound    text,
  start_lap   smallint not null,
  end_lap     smallint not null,
  primary key (event_id, session, driver_id, stint),
  check (end_lap >= start_lap)
);

-- Downsampled fastest-lap telemetry, columnar (docs/decisions/0006):
-- {"d":[m],"speed":[km/h],"throttle":[0-100],"brake":[0|1],"gear":[1-8],"x":[..],"y":[..]}
create table public.fastest_lap_traces (
  event_id     integer not null references public.events (id) on delete cascade,
  session      text not null check (session in ('Q', 'R', 'SQ', 'S')),
  driver_id    text not null references public.drivers (id),
  lap          smallint not null,
  lap_time_ms  integer not null,
  points       jsonb not null,
  primary key (event_id, session, driver_id)
);

-- ---------------------------------------------------------------- standings

-- Snapshot of the official standings after the latest ingested round (docs/decisions/0008).
create table public.standings (
  season       smallint not null references public.seasons (year),
  kind         text not null check (kind in ('driver', 'constructor')),
  entity_id    text not null,                   -- drivers.id or teams.id
  position     smallint,
  points       real not null,
  wins         smallint not null default 0,
  after_round  smallint not null,
  primary key (season, kind, entity_id)
);

-- ---------------------------------------------------------------- ETL bookkeeping

create table public.etl_runs (
  id           bigint generated always as identity primary key,
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  args         jsonb not null default '{}',
  row_counts   jsonb not null default '{}',
  status       text not null default 'running' check (status in ('running', 'ok', 'partial', 'failed')),
  error        text
);

-- ---------------------------------------------------------------- row-level security
-- Public F1 data: anyone may read, nobody but the service role / owner may write.
-- etl_runs has RLS on and no policy, so it is invisible to anon and authenticated.

do $$
declare t text;
begin
  foreach t in array array[
    'seasons', 'circuits', 'events', 'drivers', 'teams', 'driver_teams',
    'results', 'laps', 'stints', 'fastest_lap_traces', 'standings'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy "public read" on public.%I for select to anon, authenticated using (true)', t);
  end loop;
end $$;

alter table public.etl_runs enable row level security;
