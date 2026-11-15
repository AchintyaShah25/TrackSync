"use client";

import { TelemetryChart } from "@/components/charts/TelemetryChart";
import type { EventDetail, TracesResponse } from "@/lib/api/types";
import { seriesStyles } from "@/lib/charts/series";
import { formatLapTime } from "@/lib/format";
import { useTraces } from "@/lib/queries/race";
import { parseChoice, parseDriverCodes } from "@/lib/urlState";
import { useUrlState } from "@/lib/useUrlState";

import { Segmented } from "../ui/Segmented";
import { Skeleton } from "../ui/Skeleton";
import { EmptyState, ErrorState } from "../ui/States";
import { DriverPicker } from "./DriverPicker";

const SESSIONS = ["Q", "R"] as const;
const LABEL = { Q: "Qualifying", R: "Race" } as const;

export function TelemetryView({
  event,
  defaults,
  initial,
}: {
  event: EventDetail;
  defaults: { session: "Q" | "R"; codes: string[] };
  initial: TracesResponse | null;
}) {
  const { params, update } = useUrlState();
  const session = parseChoice(params.get("session") ?? undefined, SESSIONS, defaults.session);
  const urlCodes = parseDriverCodes(params.get("drivers") ?? undefined, 2);
  const codes = urlCodes.length ? urlCodes : defaults.codes;
  const query = useTraces(
    event.id,
    session,
    codes,
    initial ? { session: defaults.session, codes: defaults.codes, data: initial } : undefined,
  );

  const available = SESSIONS.filter((s) => event.trace_sessions.includes(s));
  const traces = query.data?.traces ?? [];
  const styles = seriesStyles(traces.map((t) => t.driver));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <DriverPicker drivers={event.drivers} selected={codes} max={2} onChange={(c) => update({ drivers: c })} />
        <Segmented
          label="Session"
          value={session}
          options={SESSIONS.map((s) => ({ value: s, label: LABEL[s], disabled: !available.includes(s) }))}
          onChange={(s) => update({ session: s })}
        />
      </div>

      {traces.length > 0 && (
        <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
          {traces.map((t) => (
            <div key={t.driver.id}>
              <dt className="flex items-center gap-2 text-xs text-subtle">
                <LineSwatch color={styles.get(t.driver.id)?.color} dashed={styles.get(t.driver.id)?.dashed} />
                {t.driver.full_name} · fastest lap {t.lap}
              </dt>
              <dd className="font-medium">{formatLapTime(t.lap_time_ms)}</dd>
            </div>
          ))}
          {traces.length === 2 && (
            <div>
              <dt className="text-xs text-subtle">Gap</dt>
              <dd className="font-medium">
                {(Math.abs(traces[0].lap_time_ms - traces[1].lap_time_ms) / 1000).toFixed(3)}s
              </dd>
            </div>
          )}
        </dl>
      )}

      <div aria-busy={query.isFetching} className={query.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
        {codes.length === 0 ? (
          <EmptyState title="Pick a driver">Choose one or two drivers to compare their fastest laps.</EmptyState>
        ) : query.isPending ? (
          <TelemetrySkeleton />
        ) : query.isError ? (
          <ErrorState onRetry={() => query.refetch()} />
        ) : traces.length === 0 ? (
          <EmptyState title="No telemetry for this selection">
            We store fastest-lap telemetry for qualifying and the race. Some drivers have no clean lap
            (for example a DNF on lap 1).
          </EmptyState>
        ) : (
          <TelemetryChart traces={traces} />
        )}
      </div>
      <p className="text-xs text-subtle">
        Fastest lap per driver, resampled to 300 points by distance. Hover or tap a chart to see values.
      </p>
    </div>
  );
}

/** Legend key: a short line in the series color, dashed for a same-team second driver. */
function LineSwatch({ color, dashed }: { color?: string; dashed?: boolean }) {
  return (
    <svg aria-hidden width="20" height="6" viewBox="0 0 20 6">
      <line x1="1" y1="3" x2="19" y2="3" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeDasharray={dashed ? "5 3" : undefined} />
    </svg>
  );
}

export function TelemetrySkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-56" label="Loading telemetry" />
      <Skeleton className="h-28" />
      <Skeleton className="h-16" />
      <Skeleton className="h-28" />
    </div>
  );
}
