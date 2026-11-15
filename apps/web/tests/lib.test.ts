import { describe, expect, it } from "vitest";

import type { DriverRef, EventSummary, StrategyResponse, Trace } from "@/lib/api/types";
import { seriesStyles } from "@/lib/charts/series";
import { speedColor } from "@/lib/charts/speedScale";
import { compoundColor, strategyRows, typicalStops } from "@/lib/charts/strategy";
import { mergeTraces, summarizeTrace } from "@/lib/charts/telemetry";
import { formatGap, formatLapTime, formatRaceTime, raceTimeCell } from "@/lib/format";
import { countdown, formatLocalStart, nextRace } from "@/lib/schedule";
import { parseChoice, parseDriverCodes, withParams } from "@/lib/urlState";

const driver = (id: string, code: string, team: string, color: string | null = "#FF8000"): DriverRef => ({
  id,
  code,
  full_name: id,
  number: null,
  team_id: team,
  team_name: team,
  color_hex: color,
});

describe("format", () => {
  // Why: lap and race times are the most-read numbers on every page.
  it("formats lap times, race times and gaps", () => {
    expect(formatLapTime(79327)).toBe("1:19.327");
    expect(formatLapTime(9327)).toBe("09.327");
    expect(formatLapTime(null)).toBe("–");
    expect(formatRaceTime(4480727)).toBe("1:14:40.727");
    expect(formatGap(4483391, 4480727)).toBe("+2.664s");
  });
});

describe("raceTimeCell", () => {
  const leader = { time_ms: 4480727, laps: 53 };
  // Why: Jolpica's total time for a lapped car covers fewer laps, so a time gap is wrong
  // (Monza 2024 showed Ocon, P14, at "+12.659s"); lapped cars must read "+1 lap".
  it("shows total, gap, laps down or status", () => {
    expect(raceTimeCell({ ...leader, status: "Finished" }, leader, true)).toBe("1:14:40.727");
    expect(raceTimeCell({ time_ms: 4483391, laps: 53, status: "Finished" }, leader, false)).toBe("+2.664s");
    expect(raceTimeCell({ time_ms: 4493386, laps: 52, status: "Lapped" }, leader, false)).toBe("+1 lap");
    expect(raceTimeCell({ time_ms: 4493386, laps: 51, status: "Lapped" }, leader, false)).toBe("+2 laps");
    expect(raceTimeCell({ time_ms: null, laps: 20, status: "Retired" }, leader, false)).toBe("Retired");
  });
});

describe("urlState", () => {
  // Why: shared URLs are user input; bad values must fall back, not crash the page.
  it("parses driver codes: uppercases, dedupes, validates and caps", () => {
    expect(parseDriverCodes("ver,NOR,ver")).toEqual(["VER", "NOR"]);
    expect(parseDriverCodes("VER,NOR,LEC", 2)).toEqual(["VER", "NOR"]);
    expect(parseDriverCodes("x1,<script>")).toEqual([]);
    expect(parseDriverCodes(undefined)).toEqual([]);
  });

  // Why: session pickers must only accept sessions the API serves.
  it("falls back to the default for unknown choices", () => {
    expect(parseChoice("r", ["Q", "R"] as const, "Q")).toBe("R");
    expect(parseChoice("FP1", ["Q", "R"] as const, "Q")).toBe("Q");
  });

  // Why: control changes rewrite the query string; untouched keys must survive.
  it("updates query strings, keeping other keys and dropping empty ones", () => {
    expect(withParams("session=Q&x=1", { drivers: ["VER", "NOR"] })).toBe(
      "?session=Q&x=1&drivers=VER%2CNOR",
    );
    expect(withParams("session=Q", { session: undefined })).toBe("");
  });
});

describe("series", () => {
  // Why: two drivers from one team share a color, so the second must be dashed to be told apart.
  it("dashes the second driver of the same team and falls back on missing colors", () => {
    const styles = seriesStyles([
      driver("norris", "NOR", "mclaren"),
      driver("piastri", "PIA", "mclaren"),
      driver("sainz", "SAI", "williams", null),
    ]);
    expect(styles.get("norris")).toEqual({ color: "#FF8000", dashed: false });
    expect(styles.get("piastri")?.dashed).toBe(true);
    expect(styles.get("sainz")?.color).toBe("var(--chart-fallback-series)");
  });
});

describe("telemetry", () => {
  const trace = (id: string, speed: number[]): Trace => ({
    driver: driver(id, id.slice(0, 3).toUpperCase(), id),
    lap: 1,
    lap_time_ms: 80000,
    points: {
      d: [0, 10, 20, 30],
      speed,
      throttle: [100, 100, 40, 100],
      brake: [0, 1, 1, 0],
      gear: [7, 6, 4, 6],
      x: [0, 0, 0, 0],
      y: [0, 0, 0, 0],
    },
  });

  // Why: Recharts needs one row per x value with every driver's channels side by side.
  it("merges traces on the shared distance grid", () => {
    const rows = mergeTraces([trace("norris", [300, 200, 100, 250]), trace("leclerc", [301, 199, 98, 251])]);
    expect(rows).toHaveLength(4);
    expect(rows[2]).toMatchObject({ d: 20, "norris:speed": 100, "leclerc:speed": 98, "norris:gear": 4 });
    expect(mergeTraces([])).toEqual([]);
  });

  // Why: the chart's accessible text summary is built from these numbers.
  it("summarizes top speed, full-throttle share and braking zones", () => {
    expect(summarizeTrace(trace("norris", [300, 200, 100, 250]))).toEqual({
      driverId: "norris",
      topSpeed: 300,
      fullThrottlePct: 75,
      brakingZones: 1,
    });
  });
});

describe("strategy", () => {
  const data: StrategyResponse = {
    session: "R",
    total_laps: 53,
    drivers: [driver("leclerc", "LEC", "ferrari"), driver("norris", "NOR", "mclaren")],
    finish_position: { leclerc: 1, norris: null },
    stints: [
      { driver_id: "norris", stint: 2, compound: "HARD", start_lap: 15, end_lap: 53 },
      { driver_id: "norris", stint: 1, compound: "MEDIUM", start_lap: 1, end_lap: 14 },
      { driver_id: "leclerc", stint: 1, compound: "MEDIUM", start_lap: 1, end_lap: 15 },
      { driver_id: "leclerc", stint: 2, compound: "HARD", start_lap: 16, end_lap: 53 },
    ],
  };

  // Why: the timeline draws bars from these offsets; an off-by-one shifts every pit stop.
  it("builds ordered stint bars with zero-based starts and stop counts", () => {
    const rows = strategyRows(data);
    expect(rows.map((r) => r.driver.id)).toEqual(["leclerc", "norris"]);
    expect(rows[1].stints).toEqual([
      { stint: 1, compound: "MEDIUM", start: 0, laps: 14 },
      { stint: 2, compound: "HARD", start: 14, laps: 39 },
    ]);
    expect(rows[1].position).toBeNull();
    expect(typicalStops(rows)).toBe(1);
  });

  // Why: compound colors are fixed data colors and must come from tokens (dark mode).
  it("maps compounds to tokens with an unknown fallback", () => {
    expect(compoundColor("soft")).toBe("var(--tyre-soft)");
    expect(compoundColor(null)).toBe("var(--tyre-unknown)");
  });
});

describe("speed scale", () => {
  // Why: the track map legend and segments must agree at the ends of the ramp.
  it("clamps and interpolates the ramp", () => {
    expect(speedColor(-1)).toBe(speedColor(0));
    expect(speedColor(2)).toBe("rgb(253, 231, 37)");
    expect(speedColor(0)).toBe("rgb(49, 54, 149)");
  });
});

describe("schedule", () => {
  const ev = (round: number, iso: string | null): EventSummary => ({
    id: 202600 + round,
    season: 2026,
    round,
    name: `Round ${round}`,
    slug: `round-${round}`,
    format: "conventional",
    circuit_id: "x",
    circuit_name: "X",
    locality: null,
    country: null,
    race_start_utc: iso,
    sessions: [],
    has_data: false,
  });

  // Why: the landing page countdown must pick the right upcoming race from a static list.
  it("finds the next race after now, ignoring past and undated events", () => {
    const events = [ev(21, "2026-11-22T04:00:00Z"), ev(20, "2026-11-08T17:00:00Z"), ev(23, null)];
    expect(nextRace(events, new Date("2026-11-14T00:00:00Z"))?.round).toBe(21);
    expect(nextRace(events, new Date("2026-12-31T00:00:00Z"))).toBeNull();
  });

  // Why: the countdown ticks client-side; it must never go negative after lights out.
  it("computes countdown parts and clamps at zero", () => {
    const now = new Date("2026-11-20T02:58:30Z");
    expect(countdown(new Date("2026-11-22T04:00:00Z"), now)).toEqual({
      days: 2,
      hours: 1,
      minutes: 1,
      seconds: 30,
      done: false,
    });
    expect(countdown(new Date("2026-11-01T00:00:00Z"), now).done).toBe(true);
  });

  // Why: the race start is shown in the viewer's local time zone (SPEC M1).
  it("formats the start in the viewer's time zone", () => {
    const s = formatLocalStart("2026-11-22T04:00:00Z", "en-US", "America/Los_Angeles");
    expect(s).toContain("Nov 21");
    expect(s).toContain("8:00");
  });
});
