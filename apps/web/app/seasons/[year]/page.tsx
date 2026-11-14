import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StandingsTables } from "@/components/race/StandingsTables";
import { SectionTitle } from "@/components/ui/Card";
import { cn } from "@/components/ui/cn";
import { paths } from "@/lib/api/client";
import { serverGetOrNull } from "@/lib/api/server";
import type { EventSummary, StandingsResponse } from "@/lib/api/types";
import { FIRST_SEASON, LAST_SEASON } from "@/lib/race";

export const revalidate = 86400;

const SEASONS = Array.from({ length: LAST_SEASON - FIRST_SEASON + 1 }, (_, i) => LAST_SEASON - i);

export function generateStaticParams() {
  return SEASONS.map((y) => ({ year: String(y) }));
}

export async function generateMetadata({ params }: PageProps<"/seasons/[year]">): Promise<Metadata> {
  const { year } = await params;
  return { title: `${year} season` };
}

export default async function SeasonPage({ params }: PageProps<"/seasons/[year]">) {
  const year = Number((await params).year);
  if (!SEASONS.includes(year)) notFound();
  const [events, standings] = await Promise.all([
    serverGetOrNull<EventSummary[]>(paths.events(year)),
    serverGetOrNull<StandingsResponse>(paths.standings(year)),
  ]);
  if (!events) notFound();
  const fmt = new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" });

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{year} season</h1>
        <nav aria-label="Seasons" className="flex flex-wrap gap-1">
          {SEASONS.map((y) => (
            <Link
              key={y}
              href={`/seasons/${y}`}
              aria-current={y === year ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm",
                y === year ? "bg-surface-muted font-medium" : "text-muted hover:text-fg",
              )}
            >
              {y}
            </Link>
          ))}
        </nav>
      </div>

      <section aria-labelledby="calendar" className="flex flex-col gap-3">
        <SectionTitle id="calendar">Races</SectionTitle>
        <ol className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {events.map((e) => {
            const body = (
              <>
                <span className="text-xs text-subtle">
                  R{e.round} · {e.race_start_utc ? fmt.format(new Date(e.race_start_utc)) : "TBC"}
                  {e.format === "sprint" ? " · Sprint" : ""}
                </span>
                <span className="font-medium">{e.name.replace(" Grand Prix", " GP")}</span>
                <span className="text-xs text-muted">{e.locality ?? e.circuit_name}</span>
              </>
            );
            return (
              <li key={e.id} className="bg-surface">
                {e.has_data ? (
                  <Link href={`/races/${e.season}/${e.round}`} className="flex h-full flex-col gap-0.5 p-4 hover:bg-surface-muted">
                    {body}
                  </Link>
                ) : (
                  <div className="flex h-full flex-col gap-0.5 p-4 opacity-60" aria-label={`${e.name}: no data yet`}>
                    {body}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      <section aria-labelledby="standings" className="flex flex-col gap-3">
        <SectionTitle id="standings">
          Standings{standings ? <span className="ml-2 text-sm font-normal text-subtle">after round {standings.after_round}</span> : null}
        </SectionTitle>
        {standings ? (
          <StandingsTables standings={standings} />
        ) : (
          <p className="text-sm text-muted">Standings are not available for this season yet.</p>
        )}
      </section>
    </div>
  );
}
