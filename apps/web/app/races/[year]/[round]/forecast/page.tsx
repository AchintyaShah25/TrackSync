import type { Metadata } from "next";
import { Suspense } from "react";

import { ForecastView, type ForecastDefaults } from "@/components/race/ForecastView";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/States";
import { paths } from "@/lib/api/client";
import { serverGetOrNull, serverPostOrNull } from "@/lib/api/server";
import type { EventDetail, ModelSummary, SimulateResponse, StrategyResponse } from "@/lib/api/types";
import {
  actualStints,
  buildRequest,
  defaultStrategies,
  isWetRace,
  parseStints,
  strategyLabel,
} from "@/lib/charts/forecast";
import { loadEvent } from "@/lib/race";
import { SHOWCASE, showcasePreset } from "@/lib/showcase";

export const revalidate = 86400;

export function generateStaticParams() {
  return SHOWCASE.filter((e) => e.view === "forecast").map((e) => ({
    year: String(e.season),
    round: String(e.round),
  }));
}

type Props = PageProps<"/races/[year]/[round]/forecast">;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const event = await loadEvent(params);
  return { title: `Strategy forecast · ${event.season} ${event.name}` };
}

function defaultsFor(event: EventDetail, stints: StrategyResponse): ForecastDefaults | null {
  const total = stints.total_laps;
  const finishers = event.drivers.filter(
    (d) => actualStints(stints.stints, d.id, total) && stints.finish_position[d.id] != null,
  );
  const preset = showcasePreset(event.season, event.round, "forecast");
  const driver = finishers.find((d) => d.code === preset?.drivers[0]) ?? finishers[0];
  if (!driver) return null;
  const presetStrategies = preset?.strategies?.map(parseStints).filter((s) => s !== null) ?? [];
  return {
    driverCode: driver.code,
    strategies: presetStrategies.length
      ? presetStrategies
      : defaultStrategies(actualStints(stints.stints, driver.id, total), total),
    safetyCars: preset?.safetyCars ?? "random",
  };
}

export default async function ForecastPage({ params }: Props) {
  const event = await loadEvent(params);
  const stints = event.total_laps ? await serverGetOrNull<StrategyResponse>(paths.stints(event.id, "R")) : null;
  if (!stints || stints.stints.length === 0) {
    return (
      <EmptyState title="Forecasts cover past races">
        Strategy forecasts need the race&apos;s lap data, which arrives with the weekly update after the race.
      </EmptyState>
    );
  }
  if (isWetRace(stints.stints)) {
    return (
      <EmptyState title="Forecasts cover dry races only">
        This race was run partly on intermediate or wet tyres, which the tyre model does not cover.
      </EmptyState>
    );
  }
  const model = await serverGetOrNull<ModelSummary>(paths.modelParams(event.circuit_id));
  const defaults = defaultsFor(event, stints);
  if (!model || !defaults) {
    return (
      <EmptyState title="Forecast not available yet">
        The race model for this circuit has not been fitted yet. It updates with the weekly data refresh.
      </EmptyState>
    );
  }
  // Showcase races are simulated at build time, so they render instantly with the API asleep.
  let initial = null;
  if (showcasePreset(event.season, event.round, "forecast")) {
    const driver = event.drivers.find((d) => d.code === defaults.driverCode)!;
    const request = buildRequest(
      event.id,
      driver.id,
      defaults.strategies.map((s, i) => ({ label: strategyLabel(i), stints: s })),
      defaults.safetyCars,
    );
    const data = await serverPostOrNull<SimulateResponse>(paths.simulate(), request);
    initial = data ? { request, data } : null;
  }
  return (
    <Suspense fallback={<Skeleton className="h-[720px]" label="Loading strategy forecast" />}>
      <ForecastView event={event} stints={stints} model={model} defaults={defaults} initial={initial} />
    </Suspense>
  );
}
