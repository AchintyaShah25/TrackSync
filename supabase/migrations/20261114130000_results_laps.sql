-- Laps completed per driver (race/sprint). Lapped cars' Jolpica total time covers fewer laps,
-- so the UI shows "+N laps" from this instead of a misleading time gap.
alter table public.results add column laps smallint check (laps >= 0);
