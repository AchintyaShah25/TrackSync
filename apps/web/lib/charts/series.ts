import type { DriverRef } from "../api/types";

export interface SeriesStyle {
  color: string;
  dashed: boolean;
}

/**
 * Team color per driver; when two selected drivers share a team, later ones are dashed
 * (new-chart skill §3). Missing colors fall back to the neutral token.
 */
export function seriesStyles(drivers: DriverRef[]): Map<string, SeriesStyle> {
  const seenTeams = new Set<string>();
  const out = new Map<string, SeriesStyle>();
  for (const d of drivers) {
    const team = d.team_id ?? d.id;
    out.set(d.id, {
      color: d.color_hex ?? "var(--chart-fallback-series)",
      dashed: seenTeams.has(team),
    });
    seenTeams.add(team);
  }
  return out;
}
