// Strategy forecaster helpers: URL codec, validation (mirrors racemodel.validate_strategy),
// presets and the fan-chart transform. Pure functions; unit-tested in tests/lib.test.ts.

import type {
  DryCompound,
  SafetyCarMode,
  SimulateRequest,
  SimulateResponse,
  StintIn,
  StintRow,
  StrategyIn,
} from "../api/types";

export const DRY: DryCompound[] = ["SOFT", "MEDIUM", "HARD"];
export const MAX_STRATEGIES = 3;
export const MAX_STINTS = 5;
export const RUNS = 500;
export const SEED = 7; // fixed so shared links and static pages reproduce exactly
export const STRATEGY_COLORS = ["var(--chart-strategy-1)", "var(--chart-strategy-2)", "var(--chart-strategy-3)"];
export const BAND_OUTER_OPACITY = 0.14;
export const BAND_INNER_OPACITY = 0.3;

const LETTER: Record<DryCompound, string> = { SOFT: "S", MEDIUM: "M", HARD: "H" };
const FROM_LETTER: Record<string, DryCompound> = { S: "SOFT", M: "MEDIUM", H: "HARD" };
const WET = new Set(["INTERMEDIATE", "WET"]);

/** [{MEDIUM,20},{HARD,33}] → "M20-H33" */
export function encodeStints(stints: StintIn[]): string {
  return stints.map((s) => `${LETTER[s.compound]}${s.laps}`).join("-");
}

/** "M20-H33" → stints, or null if malformed. */
export function parseStints(value: string | null | undefined): StintIn[] | null {
  if (!value) return null;
  const parts = value.toUpperCase().split("-");
  if (parts.length < 1 || parts.length > MAX_STINTS) return null;
  const out: StintIn[] = [];
  for (const p of parts) {
    const m = /^([SMH])(\d{1,3})$/.exec(p);
    if (!m) return null;
    const laps = Number(m[2]);
    if (laps < 1 || laps > 100) return null;
    out.push({ compound: FROM_LETTER[m[1]], laps });
  }
  return out;
}

/** Problems with a dry strategy (empty = valid). Same rules as the API (decision 0021). */
export function strategyErrors(stints: StintIn[], totalLaps: number): string[] {
  const errors: string[] = [];
  if (!stints.length) return ["Add at least one stint."];
  const laps = stints.reduce((n, s) => n + s.laps, 0);
  if (laps !== totalLaps) {
    const diff = totalLaps - laps;
    errors.push(diff > 0 ? `${diff} more lap${diff === 1 ? "" : "s"} needed (race is ${totalLaps}).` : `${-diff} lap${diff === -1 ? "" : "s"} too many (race is ${totalLaps}).`);
  }
  if (new Set(stints.map((s) => s.compound)).size < 2) {
    errors.push("A dry race must use at least two different compounds.");
  }
  if (stints.some((s) => s.laps < 1)) errors.push("Every stint needs at least one lap.");
  return errors;
}

/** Split `total` laps into parts proportional to `weights`, summing exactly to total. */
export function splitLaps(total: number, weights: number[]): number[] {
  const sum = weights.reduce((a, b) => a + b, 0);
  const raw = weights.map((w) => (w / sum) * total);
  const out = raw.map(Math.floor);
  let rest = total - out.reduce((a, b) => a + b, 0);
  const order = raw.map((r, i) => [r - Math.floor(r), i] as const).sort((a, b) => b[0] - a[0]);
  for (const [, i] of order) {
    if (rest-- <= 0) break;
    out[i] += 1;
  }
  return out;
}

export function oneStop(totalLaps: number): StintIn[] {
  const [a, b] = splitLaps(totalLaps, [0.4, 0.6]);
  return [
    { compound: "MEDIUM", laps: a },
    { compound: "HARD", laps: b },
  ];
}

export function twoStop(totalLaps: number): StintIn[] {
  const [a, b, c] = splitLaps(totalLaps, [0.3, 0.4, 0.3]);
  return [
    { compound: "MEDIUM", laps: a },
    { compound: "HARD", laps: b },
    { compound: "MEDIUM", laps: c },
  ];
}

/** A driver's real race strategy from the stints feed, if it was all dry tyres. */
export function actualStints(rows: StintRow[], driverId: string, totalLaps: number): StintIn[] | null {
  const mine = rows.filter((r) => r.driver_id === driverId).sort((a, b) => a.start_lap - b.start_lap);
  if (!mine.length || mine.some((r) => !DRY.includes(r.compound as DryCompound))) return null;
  const stints = mine.map((r) => ({ compound: r.compound as DryCompound, laps: r.end_lap - r.start_lap + 1 }));
  const covered = stints.reduce((n, s) => n + s.laps, 0);
  const last = stints[stints.length - 1];
  last.laps += totalLaps - covered; // lapped finishers: extend to race distance (as the API does)
  return last.laps >= 1 ? stints : null;
}

/** Same rule as racemodel.dataset.wet_events: more than 10% of race laps on wet tyres. */
export function isWetRace(rows: StintRow[]): boolean {
  let wet = 0;
  let all = 0;
  for (const r of rows) {
    const laps = r.end_lap - r.start_lap + 1;
    all += laps;
    if (WET.has((r.compound ?? "").toUpperCase())) wet += laps;
  }
  return all > 0 && wet > 0.1 * all;
}

export function buildRequest(
  eventId: number,
  driverId: string,
  strategies: StrategyIn[],
  safetyCars: SafetyCarMode,
): SimulateRequest {
  return { event_id: eventId, driver_id: driverId, strategies, runs: RUNS, seed: SEED, safety_cars: safetyCars };
}

export const strategyLabel = (i: number) => `Strategy ${String.fromCharCode(65 + i)}`;

export interface FanRow {
  lap: number;
  sc?: number; // share of runs under SC or VSC on this lap, 0-1
  [key: string]: number | [number, number] | undefined;
}

/**
 * Per-lap rows for the fan chart. Values are seconds AHEAD of the driver's real strategy
 * (positive = better), so the API's gap (positive = behind) is negated and its bands flip.
 */
export function fanRows(data: SimulateResponse): FanRow[] {
  return Array.from({ length: data.total_laps }, (_, i) => {
    const row: FanRow = { lap: i + 1, sc: round(data.sc_share[i] + data.vsc_share[i], 3) };
    data.strategies.forEach((s, k) => {
      row[`s${k}_outer`] = [round(-s.gap.p90[i]), round(-s.gap.p10[i])];
      row[`s${k}_inner`] = [round(-s.gap.p75[i]), round(-s.gap.p25[i])];
      row[`s${k}_mid`] = round(-s.gap.p50[i]);
    });
    return row;
  });
}

const round = (v: number, d = 2) => Math.round(v * 10 ** d) / 10 ** d;

/** "+2.3 s faster" style text for a finish-time delta (API sign: negative = faster). */
export function formatDelta(deltaS: number): string {
  const v = Math.abs(deltaS);
  if (v < 0.05) return "level";
  return `${v.toFixed(1)} s ${deltaS < 0 ? "faster" : "slower"}`;
}

export const pct = (p: number | null) => (p == null ? "–" : `${Math.round(p * 100)}%`);

/** Text summary for screen readers and the figure's aria-label. */
export function describeForecast(data: SimulateResponse): string {
  const parts = data.strategies.map((s) => {
    const d = s.finish_delta_s;
    return `${s.label} (${encodeStints(s.stints)}): median ${formatDelta(d.p50)} than the real strategy, 90% range ${formatDelta(d.p5)} to ${formatDelta(d.p95)}`;
  });
  return `Strategy forecast for ${data.driver.full_name} over ${data.runs} simulated races. ${parts.join(". ")}.`;
}

/** Default strategies to show: two standard alternatives, skipping any that equal the real one. */
export function defaultStrategies(actual: StintIn[] | null, totalLaps: number): StintIn[][] {
  const real = actual ? encodeStints(actual) : "";
  const candidates = [oneStop(totalLaps), twoStop(totalLaps), [
    { compound: "HARD" as const, laps: splitLaps(totalLaps, [0.55, 0.45])[0] },
    { compound: "MEDIUM" as const, laps: splitLaps(totalLaps, [0.55, 0.45])[1] },
  ]];
  return candidates.filter((s) => encodeStints(s) !== real).slice(0, 2);
}
