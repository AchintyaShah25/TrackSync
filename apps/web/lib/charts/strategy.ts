import type { DriverRef, StrategyResponse } from "../api/types";

export const COMPOUNDS = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"] as const;

export function compoundColor(compound: string | null): string {
  switch ((compound ?? "").toUpperCase()) {
    case "SOFT":
      return "var(--tyre-soft)";
    case "MEDIUM":
      return "var(--tyre-medium)";
    case "HARD":
      return "var(--tyre-hard)";
    case "INTERMEDIATE":
      return "var(--tyre-intermediate)";
    case "WET":
      return "var(--tyre-wet)";
    default:
      return "var(--tyre-unknown)";
  }
}

export function compoundLabel(compound: string | null): string {
  const c = (compound ?? "").toUpperCase();
  return c === "INTERMEDIATE" ? "Inter" : c ? c[0] + c.slice(1).toLowerCase() : "Unknown";
}

export interface StintBar {
  stint: number;
  compound: string | null;
  start: number; // lap index the stint starts at (start_lap - 1)
  laps: number;
}

export interface StrategyRow {
  driver: DriverRef;
  position: number | null;
  stints: StintBar[];
  stops: number;
}

/** One row per driver in finishing order with contiguous stint bars. */
export function strategyRows(data: StrategyResponse): StrategyRow[] {
  const byDriver = new Map<string, StintBar[]>();
  for (const s of data.stints) {
    const list = byDriver.get(s.driver_id) ?? [];
    list.push({
      stint: s.stint,
      compound: s.compound,
      start: s.start_lap - 1,
      laps: s.end_lap - s.start_lap + 1,
    });
    byDriver.set(s.driver_id, list);
  }
  return data.drivers.map((driver) => {
    const stints = (byDriver.get(driver.id) ?? []).sort((a, b) => a.start - b.start);
    return {
      driver,
      position: data.finish_position[driver.id] ?? null,
      stints,
      stops: Math.max(stints.length - 1, 0),
    };
  });
}

/** Most common stop count, for the chart summary ("Most drivers made 1 stop"). */
export function typicalStops(rows: StrategyRow[]): number | null {
  if (rows.length === 0) return null;
  const counts = new Map<number, number>();
  for (const r of rows) counts.set(r.stops, (counts.get(r.stops) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
}
