import type { StandingsResponse } from "@/lib/api/types";
import { formatPoints } from "@/lib/format";

function Swatch({ color }: { color: string | null }) {
  return (
    <span aria-hidden className="inline-block h-3 w-1 rounded-full" style={{ background: color ?? "var(--chart-fallback-series)" }} />
  );
}

export function StandingsTables({ standings }: { standings: StandingsResponse }) {
  return (
    <div className="grid gap-10 lg:grid-cols-2">
      <section aria-labelledby="drivers-standings">
        <h3 id="drivers-standings" className="mb-3 font-medium">Drivers</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-subtle">
              <th scope="col" className="w-10 py-2 font-normal">Pos</th>
              <th scope="col" className="py-2 font-normal">Driver</th>
              <th scope="col" className="py-2 text-right font-normal">Wins</th>
              <th scope="col" className="py-2 text-right font-normal">Pts</th>
            </tr>
          </thead>
          <tbody>
            {standings.drivers.map((s) => (
              <tr key={s.driver.id} className="border-b border-border last:border-0">
                <td className="py-2 text-muted">{s.position ?? "–"}</td>
                <td className="py-2">
                  <span className="flex items-center gap-2">
                    <Swatch color={s.driver.color_hex} />
                    <span className="font-medium">{s.driver.full_name}</span>
                    <span className="hidden text-xs text-subtle sm:inline">{s.driver.team_name}</span>
                  </span>
                </td>
                <td className="py-2 text-right text-muted">{s.wins}</td>
                <td className="py-2 text-right font-medium">{formatPoints(s.points)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section aria-labelledby="constructors-standings">
        <h3 id="constructors-standings" className="mb-3 font-medium">Constructors</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-subtle">
              <th scope="col" className="w-10 py-2 font-normal">Pos</th>
              <th scope="col" className="py-2 font-normal">Team</th>
              <th scope="col" className="py-2 text-right font-normal">Wins</th>
              <th scope="col" className="py-2 text-right font-normal">Pts</th>
            </tr>
          </thead>
          <tbody>
            {standings.constructors.map((s) => (
              <tr key={s.team_id} className="border-b border-border last:border-0">
                <td className="py-2 text-muted">{s.position ?? "–"}</td>
                <td className="py-2">
                  <span className="flex items-center gap-2">
                    <Swatch color={s.color_hex} />
                    <span className="font-medium">{s.team_name}</span>
                  </span>
                </td>
                <td className="py-2 text-right text-muted">{s.wins}</td>
                <td className="py-2 text-right font-medium">{formatPoints(s.points)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
