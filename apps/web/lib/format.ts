/** 79327 → "1:19.327" */
export function formatLapTime(ms: number | null | undefined): string {
  if (ms == null) return "–";
  const minutes = Math.floor(ms / 60_000);
  const seconds = ((ms % 60_000) / 1000).toFixed(3).padStart(6, "0");
  return minutes > 0 ? `${minutes}:${seconds}` : seconds;
}

/** Total race time 4480727 → "1:14:40.727" */
export function formatRaceTime(ms: number | null | undefined): string {
  if (ms == null) return "–";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  const s = ((ms % 60_000) / 1000).toFixed(3).padStart(6, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** Gap to the leader: "+2.664s" */
export function formatGap(ms: number | null | undefined, leaderMs: number | null | undefined) {
  if (ms == null || leaderMs == null) return null;
  return `+${((ms - leaderMs) / 1000).toFixed(3)}s`;
}

/**
 * What to show in a race result's time column: the winner's total time, the gap for cars
 * on the lead lap, "+N laps" for lapped cars (their total time covers fewer laps), else
 * the status (Retired, Disqualified, ...).
 */
export function raceTimeCell(
  row: { time_ms: number | null; laps: number | null; status: string | null },
  leader: { time_ms: number | null; laps: number | null } | undefined,
  isLeader: boolean,
): string {
  if (isLeader) return formatRaceTime(row.time_ms);
  const status = row.status ?? "–";
  if (status === "Finished") return formatGap(row.time_ms, leader?.time_ms) ?? status;
  // Only classified lapped cars ("Lapped", or Ergast-style "+1 Lap"); a retired car also
  // has fewer laps but must show its status.
  const lapped = status === "Lapped" || /^\+\d+ Laps?$/i.test(status);
  if (lapped && row.laps != null && leader?.laps != null && leader.laps > row.laps) {
    const down = leader.laps - row.laps;
    return `+${down} lap${down === 1 ? "" : "s"}`;
  }
  return status;
}

export const eventId = (season: number, round: number) => season * 100 + round;

export function formatPoints(points: number): string {
  return Number.isInteger(points) ? String(points) : points.toFixed(1);
}
