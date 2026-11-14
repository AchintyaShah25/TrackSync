import type { Metadata } from "next";
import { Suspense } from "react";

import { StrategyView } from "@/components/race/StrategyView";
import { Skeleton } from "@/components/ui/Skeleton";
import { paths } from "@/lib/api/client";
import { serverGetOrNull } from "@/lib/api/server";
import type { StrategyResponse } from "@/lib/api/types";
import { loadEvent } from "@/lib/race";
import { SHOWCASE } from "@/lib/showcase";

export const revalidate = 86400;

export function generateStaticParams() {
  return SHOWCASE.filter((e) => e.view === "strategy").map((e) => ({
    year: String(e.season),
    round: String(e.round),
  }));
}

type Props = PageProps<"/races/[year]/[round]/strategy">;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const event = await loadEvent(params);
  return { title: `Tire strategy · ${event.season} ${event.name}` };
}

export default async function StrategyPage({ params }: Props) {
  const event = await loadEvent(params);
  const initial = await serverGetOrNull<StrategyResponse>(paths.stints(event.id, "R"));
  return (
    <Suspense fallback={<Skeleton className="h-[560px]" label="Loading tire strategy" />}>
      <StrategyView event={event} initial={initial} />
    </Suspense>
  );
}
