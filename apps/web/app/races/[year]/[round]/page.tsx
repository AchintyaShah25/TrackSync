import type { Metadata } from "next";

import { ResultsTable } from "@/components/race/ResultsTable";
import { SectionTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/States";
import { paths } from "@/lib/api/client";
import { serverGetOrNull } from "@/lib/api/server";
import type { ResultRow } from "@/lib/api/types";
import { loadEvent } from "@/lib/race";
import { SHOWCASE } from "@/lib/showcase";

export const revalidate = 86400;

export function generateStaticParams() {
  const seen = new Set<string>();
  return SHOWCASE.map((e) => ({ year: String(e.season), round: String(e.round) })).filter((p) => {
    const k = `${p.year}/${p.round}`;
    return seen.has(k) ? false : (seen.add(k), true);
  });
}

export async function generateMetadata({ params }: PageProps<"/races/[year]/[round]">): Promise<Metadata> {
  const event = await loadEvent(params);
  return { title: `${event.season} ${event.name} results` };
}

export default async function RaceResultsPage({ params }: PageProps<"/races/[year]/[round]">) {
  const event = await loadEvent(params);
  const sessions = [
    { code: "R", title: "Race", kind: "race" as const },
    { code: "S", title: "Sprint", kind: "race" as const },
    { code: "Q", title: "Qualifying", kind: "qualifying" as const },
  ].filter((s) => event.data_sessions.includes(s.code));

  if (!sessions.length) {
    return (
      <EmptyState title="No results yet">
        Data appears after the weekly update following the race (Mondays, 06:00 UTC).
      </EmptyState>
    );
  }

  const results = await Promise.all(
    sessions.map((s) => serverGetOrNull<ResultRow[]>(paths.results(event.id, s.code))),
  );

  return (
    <div className="flex flex-col gap-10">
      {sessions.map((s, i) => (
        <section key={s.code} aria-labelledby={`results-${s.code}`} className="flex flex-col gap-3">
          <SectionTitle id={`results-${s.code}`}>{s.title}</SectionTitle>
          <ResultsTable rows={results[i] ?? []} kind={s.kind} />
        </section>
      ))}
    </div>
  );
}
