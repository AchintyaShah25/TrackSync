import type { Metadata } from "next";
import { Suspense } from "react";

import { TrackView } from "@/components/race/TrackView";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/States";
import { paths } from "@/lib/api/client";
import { serverGetOrNull } from "@/lib/api/server";
import type { Circuit, TracesResponse } from "@/lib/api/types";
import { loadEvent, topCodes } from "@/lib/race";
import { SHOWCASE, showcasePreset } from "@/lib/showcase";

export const revalidate = 86400;

export function generateStaticParams() {
  return SHOWCASE.filter((e) => e.view === "track").map((e) => ({
    year: String(e.season),
    round: String(e.round),
  }));
}

type Props = PageProps<"/races/[year]/[round]/track">;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const event = await loadEvent(params);
  return { title: `Track map · ${event.season} ${event.name}` };
}

export default async function TrackPage({ params }: Props) {
  const event = await loadEvent(params);
  if (event.trace_sessions.length === 0) {
    return <EmptyState title="No track data yet">The map appears after the weekly data update.</EmptyState>;
  }
  const preset = showcasePreset(event.season, event.round, "track");
  const session = preset?.session ?? (event.trace_sessions.includes("Q") ? "Q" : "R");
  const code = preset?.drivers[0] ?? (await topCodes(event, session, 1))[0] ?? null;
  const [circuit, initial] = await Promise.all([
    serverGetOrNull<Circuit>(paths.circuit(event.circuit_id)),
    code ? serverGetOrNull<TracesResponse>(paths.traces(event.id, [code], session)) : null,
  ]);
  return (
    <Suspense fallback={<Skeleton className="mx-auto aspect-[4/3] w-full max-w-3xl" label="Loading track map" />}>
      <TrackView event={event} circuit={circuit} defaults={{ session, code }} initial={initial} />
    </Suspense>
  );
}
