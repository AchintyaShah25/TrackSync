-- Fitted race model per circuit (Milestone 2, decisions 0020-0022).
-- Keyed by model_version, not season window: a refit with new logic writes new rows and
-- never overwrites what a running API reads. About 26 small rows per version.

create table public.circuit_model_params (
  circuit_id     text not null references public.circuits (id) on delete cascade,
  model_version  smallint not null check (model_version >= 1),
  params         jsonb not null,              -- racemodel.CircuitParams.to_dict()
  metrics        jsonb not null default '{}', -- n_laps, sigma, n_races, ...
  n_races        smallint not null default 0,
  n_laps         integer not null default 0,
  fitted_at      timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  primary key (circuit_id, model_version)
);

alter table public.circuit_model_params enable row level security;
create policy "public read" on public.circuit_model_params
  for select to anon, authenticated using (true);
