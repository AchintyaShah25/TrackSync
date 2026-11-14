import type { Metadata } from "next";
import { Suspense } from "react";

import { TelemetrySkeleton, TelemetryView } from "@/components/race/TelemetryView";
import { EmptyState } from "@/components/ui/States";
import { paths } from "@/lib/api/client";
import { serverGetOrNull } from "@/lib/api/server";
import type { TracesResponse } from "@/lib/api/types";
import { loadEvent, topCodes } from "@/lib/race";
import { SHOWCASE, showcasePreset } from "@/lib/showcase";

export const revalidate = 86400;

export function generateStaticParams() {
  return SHOWCASE.filter((e) => e.view === "telemetry").map((e) => ({
    year: String(e.season),
    round: String(e.round),
  }));
}

type Props = PageProps<"/races/[year]/[round]/telemetry">;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const event = await loadEvent(params);
  return { title: `Telemetry · ${event.season} ${event.name}` };
}

export default async function TelemetryPage({ params }: Props) {
  const event = await loadEvent(params);
  if (event.trace_sessions.length === 0) {
    return <EmptyState title="No telemetry yet">Telemetry appears after the weekly data update.</EmptyState>;
  }
  // Defaults are rendered at build time so the page works while the API sleeps.
  const preset = showcasePreset(event.season, event.round, "telemetry");
  const session = preset?.session ?? (event.trace_sessions.includes("Q") ? "Q" : "R");
  const codes = preset?.drivers ?? (await topCodes(event, session, 2));
  const initial = await serverGetOrNull<TracesResponse>(paths.traces(event.id, codes, session));

  return (
    <Suspense fallback={<TelemetrySkeleton />}>
      <TelemetryView event={event} defaults={{ session, codes }} initial={initial} />
    </Suspense>
  );
}
