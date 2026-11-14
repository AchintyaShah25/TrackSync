import type { ResultRow } from "@/lib/api/types";
import { formatGap, formatLapTime, formatPoints, formatRaceTime } from "@/lib/format";

export function ResultsTable({ rows, kind }: { rows: ResultRow[]; kind: "race" | "qualifying" }) {
  const leader = rows[0]?.time_ms ?? null;
  return (
    <div className="-mx-[var(--gutter)] overflow-x-auto px-[var(--gutter)]">
      <table className="w-full min-w-[30rem] text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-subtle">
            <th scope="col" className="w-10 py-2 pr-2 font-normal">Pos</th>
            <th scope="col" className="py-2 pr-2 font-normal">Driver</th>
            <th scope="col" className="hidden py-2 pr-2 font-normal sm:table-cell">Team</th>
            {kind === "race" && <th scope="col" className="py-2 pr-2 text-right font-normal">Grid</th>}
            <th scope="col" className="py-2 pr-2 text-right font-normal">{kind === "race" ? "Time / status" : "Best lap"}</th>
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
                  <span className="text-xs text-subtle">{r.driver.code}</span>
                </span>
              </td>
              <td className="hidden py-2 pr-2 text-muted sm:table-cell">{r.driver.team_name}</td>
              {kind === "race" && <td className="py-2 pr-2 text-right text-muted">{r.grid || "PL"}</td>}
              <td className="py-2 pr-2 text-right">
                {kind === "qualifying"
                  ? formatLapTime(r.time_ms)
                  : i === 0
                    ? formatRaceTime(r.time_ms)
                    : (formatGap(r.time_ms, leader) ?? r.status)}
              </td>
              {kind === "race" && <td className="py-2 text-right">{formatPoints(r.points)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
