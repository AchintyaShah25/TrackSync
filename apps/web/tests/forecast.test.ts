import { describe, expect, it } from "vitest";

import type { SimulateResponse, StintRow } from "@/lib/api/types";
import {
  actualStints,
  encodeStints,
  fanRows,
  formatDelta,
  isWetRace,
  oneStop,
  parseStints,
  splitLaps,
  strategyErrors,
  twoStop,
} from "@/lib/charts/forecast";

const stint = (driver_id: string, stint: number, compound: string | null, start_lap: number, end_lap: number): StintRow => ({
  driver_id,
  stint,
  compound,
  start_lap,
  end_lap,
});

describe("forecast URL codec", () => {
  // Why: strategies live in the URL so forecasts are shareable; links are user input.
  it("round-trips stints and rejects malformed values", () => {
    const s = [
      { compound: "MEDIUM" as const, laps: 20 },
      { compound: "HARD" as const, laps: 33 },
    ];
    expect(encodeStints(s)).toBe("M20-H33");
    expect(parseStints("m20-h33")).toEqual(s);
    for (const bad of ["", "X20-H33", "M0-H53", "M20--H33", "M20-H33-S1-S1-S1-S1", "M999", "<b>"]) {
      expect(parseStints(bad)).toBeNull();
    }
  });
});

describe("forecast validation", () => {
  // Why: the API rejects illegal strategies (user decision); the builder explains first.
  it("mirrors the API rules: lap total and two dry compounds", () => {
    expect(strategyErrors(oneStop(53), 53)).toEqual([]);
    expect(strategyErrors([{ compound: "HARD", laps: 53 }], 53)).toEqual([
      "A dry race must use at least two different compounds.",
    ]);
    expect(strategyErrors([{ compound: "HARD", laps: 20 }, { compound: "SOFT", laps: 30 }], 53)[0]).toBe(
      "3 more laps needed (race is 53).",
    );
    expect(strategyErrors([{ compound: "HARD", laps: 30 }, { compound: "SOFT", laps: 24 }], 53)[0]).toBe(
      "1 lap too many (race is 53).",
    );
  });

  // Why: presets must always be legal and cover the exact race distance.
  it("builds presets that sum to the race distance", () => {
    for (const total of [44, 53, 57, 78]) {
      expect(splitLaps(total, [0.3, 0.4, 0.3]).reduce((a, b) => a + b, 0)).toBe(total);
      expect(strategyErrors(oneStop(total), total)).toEqual([]);
      expect(strategyErrors(twoStop(total), total)).toEqual([]);
    }
  });
});

describe("forecast inputs from the stints feed", () => {
  // Why: the "Actual" preset and the overlay use the driver's real stints.
  it("extracts a driver's dry strategy and extends lapped finishers", () => {
    const rows = [stint("lec", 1, "MEDIUM", 1, 15), stint("lec", 2, "HARD", 16, 52), stint("nor", 1, "INTERMEDIATE", 1, 10)];
    expect(actualStints(rows, "lec", 53)).toEqual([
      { compound: "MEDIUM", laps: 15 },
      { compound: "HARD", laps: 38 },
    ]);
    expect(actualStints(rows, "nor", 53)).toBeNull();
    expect(actualStints(rows, "ham", 53)).toBeNull();
  });

  // Why: the page shows "dry races only" without a wasted API call, using the API's rule.
  it("flags a race as wet when more than 10% of laps were on wet tyres", () => {
    const dry = [stint("a", 1, "MEDIUM", 1, 50), stint("b", 1, "INTERMEDIATE", 1, 4)];
    const wet = [stint("a", 1, "MEDIUM", 1, 40), stint("b", 1, "INTERMEDIATE", 1, 10)];
    expect(isWetRace(dry)).toBe(false);
    expect(isWetRace(wet)).toBe(true);
  });
});

describe("fan chart transform", () => {
  // Why: the chart plots time AHEAD of the real strategy; a sign slip would invert it.
  it("negates gaps and flips band edges", () => {
    const data = {
      total_laps: 2,
      sc_share: [0, 0.5],
      vsc_share: [0, 0.1],
      strategies: [
        {
          label: "A",
          stints: [],
          stop_laps: [],
          finish_delta_s: { p5: 0, p25: 0, p50: 0, p75: 0, p95: 0 },
          gap: { p10: [1, -3], p25: [2, -2], p50: [3, -1], p75: [4, 0], p90: [5, 1] },
          positions: null,
          p_gain: null,
          p_lose: null,
        },
      ],
    } as unknown as SimulateResponse;
    const rows = fanRows(data);
    expect(rows[0]).toMatchObject({ lap: 1, sc: 0, s0_mid: -3, s0_outer: [-5, -1], s0_inner: [-4, -2] });
    expect(rows[1]).toMatchObject({ lap: 2, sc: 0.6, s0_mid: 1, s0_outer: [-1, 3] });
  });

  // Why: summary cards speak in plain words; sign conventions must not leak to users.
  it("formats deltas as faster/slower", () => {
    expect(formatDelta(-2.34)).toBe("2.3 s faster");
    expect(formatDelta(1.06)).toBe("1.1 s slower");
    expect(formatDelta(0.01)).toBe("level");
  });
});
