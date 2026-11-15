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
  laps: number | null;
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

// --- Strategy forecaster (services/api/app/schemas/strategy.py) ---

export type DryCompound = "SOFT" | "MEDIUM" | "HARD";
export type SafetyCarMode = "random" | "actual";

export interface StintIn {
  compound: DryCompound;
  laps: number;
}

export interface StrategyIn {
  label: string;
  stints: StintIn[];
}

export interface SimulateRequest {
  event_id: number;
  driver_id: string;
  strategies: StrategyIn[];
  runs: number;
  seed: number;
  safety_cars: SafetyCarMode;
}

export interface Percentiles {
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface GapBands {
  p10: number[];
  p25: number[];
  p50: number[];
  p75: number[];
  p90: number[];
}

export interface PositionProb {
  position: number;
  p: number;
}

export interface StrategyOut {
  label: string;
  stints: StintIn[];
  stop_laps: number[];
  finish_delta_s: Percentiles;
  gap: GapBands;
  positions: PositionProb[] | null;
  p_gain: number | null;
  p_lose: number | null;
}

export interface SimulateResponse {
  event_id: number;
  driver: DriverRef;
  total_laps: number;
  runs: number;
  seed: number;
  safety_cars: SafetyCarMode;
  actual: {
    stints: StintIn[];
    stop_laps: number[];
    position: number | null;
    model_position: number | null;
    race_time_s: number | null;
  };
  strategies: StrategyOut[];
  sc_share: number[];
  vsc_share: number[];
  model: { version: number; n_races: number; sigma: number; pit_loss: number; sc_rate: number; vsc_rate: number };
}

export interface DegCurve {
  compound: DryCompound;
  offset: number;
  age: number[];
  seconds: number[];
}

export interface ModelSummary {
  circuit_id: string;
  version: number;
  n_races: number;
  n_laps: number;
  fitted_at: string;
  sigma: number;
  trend: number;
  pit_loss: number;
  pit_loss_sd: number;
  sc_rate: number;
  vsc_rate: number;
  curves: DegCurve[];
}

// --- Signed-in user (services/api/app/schemas/me.py) ---

export interface Preferences {
  favorite_driver_id: string | null;
  favorite_team_id: string | null;
  theme: "light" | "dark" | "system" | null;
  units: "metric" | "imperial";
  chat_level: "beginner" | "expert";
  home_widgets: string[];
}

export interface SavedItemIn {
  kind: "chart" | "strategy";
  title: string;
  path: string;
}

export interface SavedItem extends SavedItemIn {
  id: string;
  created_at: string;
}

// --- Chat (services/api/app/schemas/chat.py) ---

export interface ChatSource {
  n: number;
  title: string;
  section: string | null;
  url: string | null;
  license: string;
  source: "fia" | "wikipedia" | "summary";
  excerpt: string;
}

export interface ChatChartSpec {
  type: "line" | "bar";
  title: string;
  x_label: string;
  y_label: string;
  series: { name: string; points: [number | string, number][] }[];
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  charts: ChatChartSpec[];
  tools_used: string[];
  provider: string;
  model: string;
}
