"use client";

import { StrategyChart } from "@/components/charts/StrategyChart";
import type { EventDetail, StrategyResponse } from "@/lib/api/types";
import { useStrategy } from "@/lib/queries/race";
import { parseChoice } from "@/lib/urlState";
import { useUrlState } from "@/lib/useUrlState";

import { Segmented } from "../ui/Segmented";
import { Skeleton } from "../ui/Skeleton";
import { EmptyState, ErrorState } from "../ui/States";

const SESSIONS = ["R", "S"] as const;

export function StrategyView({ event, initial }: { event: EventDetail; initial: StrategyResponse | null }) {
  const { params, update } = useUrlState();
  const session = parseChoice(params.get("session") ?? undefined, SESSIONS, "R");
  const query = useStrategy(event.id, session, initial ?? undefined);
  const hasSprint = event.data_sessions.includes("S");

  return (
    <div className="flex flex-col gap-6">
      {hasSprint && (
        <Segmented
          label="Session"
          value={session}
          options={[
            { value: "R", label: "Race" },
            { value: "S", label: "Sprint" },
          ]}
          onChange={(s) => update({ session: s })}
        />
      )}
      <div aria-busy={query.isFetching}>
        {query.isPending ? (
          <Skeleton className="h-[560px]" label="Loading tire strategy" />
        ) : query.isError ? (
          <ErrorState onRetry={() => query.refetch()} />
        ) : query.data.stints.length === 0 ? (
          <EmptyState title="No stint data">
            Tire data for this session isn&apos;t available yet. It arrives with the weekly update after
            the race.
          </EmptyState>
        ) : (
          <StrategyChart data={query.data} />
        )}
      </div>
      <p className="text-xs text-subtle">Drivers in finishing order. Each bar is one stint; gaps between colors are pit stops.</p>
    </div>
  );
}
