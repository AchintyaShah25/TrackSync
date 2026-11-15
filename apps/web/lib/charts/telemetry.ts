import type { Trace } from "../api/types";

export const CHANNELS = ["speed", "throttle", "brake", "gear"] as const;
export type Channel = (typeof CHANNELS)[number];

export type TelemetryRow = { d: number } & Record<string, number>;

/**
 * Merge traces (all on the same distance grid, see decision 0006) into one row per
 * distance sample: { d, "<driver>:speed": 312, ... } for Recharts.
 */
export function mergeTraces(traces: Trace[]): TelemetryRow[] {
  if (traces.length === 0) return [];
  const grid = traces[0].points.d;
  return grid.map((d, i) => {
    const row: TelemetryRow = { d };
    for (const t of traces) {
      for (const ch of CHANNELS) {
        const v = t.points[ch][i];
        if (v !== undefined) row[`${t.driver.id}:${ch}`] = v;
      }
    }
    return row;
  });
}

export const MPH_PER_KMH = 0.621371;

/** Speeds in the viewer's units (preferences): traces arrive in km/h. */
export function inUnits(traces: Trace[], units: "metric" | "imperial"): Trace[] {
  if (units === "metric") return traces;
  return traces.map((t) => ({ ...t, points: { ...t.points, speed: t.points.speed.map((v) => v * MPH_PER_KMH) } }));
}

export interface TraceSummary {
  driverId: string;
  topSpeed: number;
  fullThrottlePct: number;
  brakingZones: number;
}

/** Plain-language numbers for the chart's text summary (accessibility). */
export function summarizeTrace(t: Trace): TraceSummary {
  const { speed, throttle, brake } = t.points;
  let zones = 0;
  for (let i = 0; i < brake.length; i++) if (brake[i] && !brake[i - 1]) zones++;
  return {
    driverId: t.driver.id,
    topSpeed: Math.round(Math.max(...speed)),
    fullThrottlePct: Math.round((throttle.filter((v) => v >= 98).length / throttle.length) * 100),
    brakingZones: zones,
  };
}
