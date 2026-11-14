// Mirrors services/api/app/schemas/*.py. Keep in sync when the API changes.

export type RaceSession = "R" | "S";
export type AnySession = "R" | "S" | "Q" | "SQ";
export type TraceSession = "Q" | "R" | "SQ" | "S";

export interface DriverRef {
  id: string;
  code: string;
  full_name: string;
  number: number | null;
  team_id: string | null;
  team_name: string | null;
  color_hex: string | null;
}

export interface Season {
  year: number;
  events: number;
  completed: number;
}

export interface EventSession {
  code: string;
  name: string;
  start_utc: string;
}

export interface EventSummary {
  id: number;
  season: number;
  round: number;
  name: string;
  slug: string;
  format: string;
  circuit_id: string;
  circuit_name: string;
  locality: string | null;
  country: string | null;
  race_start_utc: string | null;
  sessions: EventSession[];
  has_data: boolean;
}

export interface EventDetail extends EventSummary {
  drivers: DriverRef[];
  data_sessions: string[];
  trace_sessions: string[];
  total_laps: number | null;
}

export interface ResultRow {
  position: number | null;
  driver: DriverRef;
  grid: number | null;
  points: number;
  status: string | null;
  time_ms: number | null;
}

export interface StintRow {
  driver_id: string;
  stint: number;
  compound: string | null;
  start_lap: number;
  end_lap: number;
}

export interface StrategyResponse {
  session: string;
  total_laps: number;
  drivers: DriverRef[];
  finish_position: Record<string, number | null>;
  stints: StintRow[];
}

export interface TracePoints {
  d: number[];
  speed: number[];
  throttle: number[];
  brake: number[];
  gear: number[];
  x: number[];
  y: number[];
}

export interface Trace {
  driver: DriverRef;
  lap: number;
  lap_time_ms: number;
  points: TracePoints;
}

export interface TracesResponse {
  event_id: number;
  session: string;
  circuit_id: string;
  traces: Trace[];
}

export interface DriverStanding {
  position: number | null;
  driver: DriverRef;
  points: number;
  wins: number;
}

export interface ConstructorStanding {
  position: number | null;
  team_id: string;
  team_name: string;
  color_hex: string | null;
  points: number;
  wins: number;
}

export interface StandingsResponse {
  season: number;
  after_round: number;
  drivers: DriverStanding[];
  constructors: ConstructorStanding[];
}

export interface Corner {
  number: number;
  letter: string;
  x: number;
  y: number;
  angle: number;
}

export interface Circuit {
  id: string;
  name: string;
  locality: string | null;
  country: string | null;
  length_m: number | null;
  outline: { x: number[]; y: number[] } | null;
  corners: Corner[];
}
