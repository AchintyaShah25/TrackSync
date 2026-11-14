"use client";

import { TrackMap } from "@/components/charts/TrackMap";
import type { Circuit, EventDetail, TracesResponse } from "@/lib/api/types";
import { formatLapTime } from "@/lib/format";
import { useTraces } from "@/lib/queries/race";
import { parseChoice, parseDriverCodes } from "@/lib/urlState";
import { useUrlState } from "@/lib/useUrlState";

import { Segmented } from "../ui/Segmented";
import { Skeleton } from "../ui/Skeleton";
import { EmptyState, ErrorState } from "../ui/States";
import { DriverPicker } from "./DriverPicker";

const SESSIONS = ["Q", "R"] as const;

export function TrackView({
  event,
  circuit,
  defaults,
  initial,
}: {
  event: EventDetail;
  circuit: Circuit | null;
  defaults: { session: "Q" | "R"; code: string | null };
  initial: TracesResponse | null;
}) {
  const { params, update } = useUrlState();
  const session = parseChoice(params.get("session") ?? undefined, SESSIONS, defaults.session);
  const urlCode = parseDriverCodes(params.get("driver") ?? undefined, 1)[0];
  const code = urlCode ?? defaults.code;
  const codes = code ? [code] : [];
  const query = useTraces(
    event.id,
    session,
    codes,
    initial && defaults.code ? { session: defaults.session, codes: [defaults.code], data: initial } : undefined,
  );
  const trace = query.data?.traces[0];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <DriverPicker
          drivers={event.drivers}
          selected={codes}
          max={1}
          label="Driver"
          onChange={(c) => update({ driver: c[0] })}
        />
        <Segmented
          label="Session"
          value={session}
          options={SESSIONS.map((s) => ({
            value: s,
            label: s === "Q" ? "Qualifying" : "Race",
            disabled: !event.trace_sessions.includes(s),
          }))}
          onChange={(s) => update({ session: s })}
        />
      </div>
      {trace && (
        <p className="text-sm text-muted">
          {trace.driver.full_name}, fastest lap {trace.lap}:{" "}
          <span className="font-medium text-fg">{formatLapTime(trace.lap_time_ms)}</span>
          {circuit?.length_m ? ` · ${(circuit.length_m / 1000).toFixed(3)} km lap` : ""}
        </p>
      )}
      <div aria-busy={query.isFetching} className="mx-auto w-full max-w-3xl">
        {!code ? (
          <EmptyState title="Pick a driver">Choose a driver to color the lap by speed.</EmptyState>
        ) : query.isPending ? (
          <Skeleton className="aspect-[4/3] w-full" label="Loading track map" />
        ) : query.isError ? (
          <ErrorState onRetry={() => query.refetch()} />
        ) : !trace ? (
          <EmptyState title="No lap for this driver">This driver has no clean fastest lap in this session.</EmptyState>
        ) : (
          <TrackMap trace={trace} circuit={circuit} />
        )}
      </div>
    </div>
  );
}
