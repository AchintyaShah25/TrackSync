-- Minimal, hand-written API test data: one finished event (2024 R16, Monza) with two
-- drivers, one future event, and an empty season.
insert into seasons (year) values (2024), (2023);

insert into circuits (id, name, locality, country, length_m, rotation_deg, outline, corners) values
  ('monza', 'Autodromo Nazionale di Monza', 'Monza', 'Italy', 5755, 95,
   '{"x":[0,1,1,0],"y":[0,0,0.5,0.5]}',
   '[{"number":1,"letter":"","x":0.1,"y":0.0,"angle":10}]'),
  ('las_vegas', 'Las Vegas Strip Street Circuit', 'Las Vegas', 'USA', null, null, null, null);

insert into events (id, season, round, circuit_id, name, slug, format, race_start_utc, sessions) values
  (202416, 2024, 16, 'monza', 'Italian Grand Prix', 'italian-grand-prix', 'conventional',
   '2024-09-01T13:00:00Z',
   '[{"code":"Q","name":"Qualifying","start_utc":"2024-08-31T14:00:00+00:00"},
     {"code":"R","name":"Race","start_utc":"2024-09-01T13:00:00+00:00"}]'),
  (202422, 2024, 22, 'las_vegas', 'Las Vegas Grand Prix', 'las-vegas-grand-prix', 'conventional',
   '2099-11-23T06:00:00Z', '[]');

insert into drivers (id, code, full_name, number) values
  ('leclerc', 'LEC', 'Charles Leclerc', 16),
  ('norris', 'NOR', 'Lando Norris', 4);

insert into teams (id, season, name, color_hex) values
  ('ferrari', 2024, 'Ferrari', '#E80020'),
  ('mclaren', 2024, 'McLaren', '#FF8000');

insert into driver_teams (driver_id, season, team_id) values
  ('leclerc', 2024, 'ferrari'), ('norris', 2024, 'mclaren');

insert into results (event_id, session, driver_id, team_id, position, grid, points, status, time_ms, laps) values
  (202416, 'R', 'leclerc', 'ferrari', 1, 4, 25, 'Finished', 4480727, 53),
  (202416, 'R', 'norris', 'mclaren', 3, 1, 16, 'Lapped', 4486880, 52),
  (202416, 'Q', 'norris', 'mclaren', 1, null, 0, null, 79327, null),
  (202416, 'Q', 'leclerc', 'ferrari', 4, null, 0, null, 79519, null);

insert into laps (event_id, session, driver_id, lap, lap_time_ms, compound, tyre_life, stint,
                  position, pit_in, pit_out, track_status, is_accurate)
select 202416, 'R', d, lap, 85000 + lap * 10, case when lap <= 2 then 'MEDIUM' else 'HARD' end,
       lap, case when lap <= 2 then 1 else 2 end, 1, lap = 2, lap = 3, '1', lap > 1 and lap not in (2, 3)
from unnest(array['leclerc', 'norris']) d, generate_series(1, 5) lap;

insert into stints (event_id, session, driver_id, stint, compound, start_lap, end_lap) values
  (202416, 'R', 'leclerc', 1, 'MEDIUM', 1, 2), (202416, 'R', 'leclerc', 2, 'HARD', 3, 5),
  (202416, 'R', 'norris', 1, 'MEDIUM', 1, 2), (202416, 'R', 'norris', 2, 'HARD', 3, 5);

insert into fastest_lap_traces (event_id, session, driver_id, lap, lap_time_ms, points) values
  (202416, 'Q', 'norris', 18, 79327,
   '{"d":[0,10,20],"speed":[300,310,320],"throttle":[100,100,100],"brake":[0,0,1],"gear":[7,8,8],"x":[0,0.5,1],"y":[0,0.2,0.4]}'),
  (202416, 'Q', 'leclerc', 17, 79519,
   '{"d":[0,10,20],"speed":[298,309,321],"throttle":[100,99,100],"brake":[0,0,1],"gear":[7,8,8],"x":[0,0.5,1],"y":[0,0.2,0.4]}');

insert into standings (season, kind, entity_id, position, points, wins, after_round) values
  (2024, 'driver', 'norris', 1, 100, 2, 16), (2024, 'driver', 'leclerc', 2, 90, 1, 16),
  (2024, 'constructor', 'mclaren', 1, 200, 3, 16), (2024, 'constructor', 'ferrari', 2, 180, 2, 16);
