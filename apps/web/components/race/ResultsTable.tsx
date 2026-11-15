import type { ResultRow } from "@/lib/api/types";
import { formatLapTime, formatPoints, raceTimeCell } from "@/lib/format";

export function ResultsTable({ rows, kind }: { rows: ResultRow[]; kind: "race" | "qualifying" }) {
  const leader = rows[0];
  return (
    <div className="-mx-[var(--gutter)] overflow-x-auto px-[var(--gutter)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-subtle">
            <th scope="col" className="w-10 py-2 pr-2 font-normal">Pos</th>
            <th scope="col" className="py-2 pr-2 font-normal">Driver</th>
            <th scope="col" className="hidden py-2 pr-2 font-normal sm:table-cell">Team</th>
            {kind === "race" && <th scope="col" className="hidden py-2 pr-2 text-right font-normal sm:table-cell">Grid</th>}
            <th scope="col" className="py-2 pr-2 text-right font-normal">{kind === "race" ? "Time" : "Best lap"}</th>
            {kind === "race" && <th scope="col" className="py-2 text-right font-normal">Pts</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.driver.id} className="border-b border-border last:border-0">
              <td className="py-2 pr-2 text-muted">{r.position ?? "–"}</td>
              <td className="py-2 pr-2">
                <span className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="inline-block h-3 w-1 rounded-full"
                    style={{ background: r.driver.color_hex ?? "var(--chart-fallback-series)" }}
                  />
                  <span className="font-medium">{r.driver.full_name}</span>
                  <span className="hidden text-xs text-subtle sm:inline">{r.driver.code}</span>
                </span>
              </td>
              <td className="hidden py-2 pr-2 text-muted sm:table-cell">{r.driver.team_name}</td>
              {kind === "race" && <td className="hidden py-2 pr-2 text-right text-muted sm:table-cell">{r.grid || "PL"}</td>}
              <td className="py-2 pr-2 text-right">
                {kind === "qualifying" ? formatLapTime(r.time_ms) : raceTimeCell(r, leader, i === 0)}
              </td>
              {kind === "race" && <td className="py-2 text-right">{formatPoints(r.points)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
