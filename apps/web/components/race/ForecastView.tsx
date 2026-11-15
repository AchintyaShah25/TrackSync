"use client";

import { useMemo, useState } from "react";

import { FanChart } from "@/components/charts/FanChart";
import { FinishDistribution } from "@/components/charts/FinishDistribution";
import { SaveButton } from "@/components/auth/SaveButton";
import { StrategyBuilder } from "@/components/forecast/StrategyBuilder";
import { ApiError } from "@/lib/api/client";
import type {
  EventDetail,
  ModelSummary,
  SafetyCarMode,
  SimulateRequest,
  SimulateResponse,
  StintIn,
  StrategyResponse,
} from "@/lib/api/types";
import {
  actualStints,
  buildRequest,
  encodeStints,
  formatDelta,
  MAX_STRATEGIES,
  parseStints,
  pct,
  STRATEGY_COLORS,
  strategyErrors,
  strategyLabel,
} from "@/lib/charts/forecast";
import { compoundColor } from "@/lib/charts/strategy";
import { useForecast } from "@/lib/queries/forecast";
import { usePreferences } from "@/lib/queries/me";
import { parseChoice, parseDriverCodes } from "@/lib/urlState";
import { useUrlState } from "@/lib/useUrlState";

import { Button } from "../ui/Button";
import { Segmented } from "../ui/Segmented";
import { Skeleton } from "../ui/Skeleton";
import { EmptyState, ErrorState } from "../ui/States";
import { DriverPicker } from "./DriverPicker";

export interface ForecastDefaults {
  driverCode: string;
  strategies: StintIn[][];
  safetyCars: SafetyCarMode;
}

const SC_MODES = ["RANDOM", "ACTUAL"] as const;
const STRATEGY_KEYS = ["s1", "s2", "s3"] as const;

export function ForecastView({
  event,
  stints,
  model,
  defaults,
  initial,
}: {
  event: EventDetail;
  stints: StrategyResponse;
  model: ModelSummary;
  defaults: ForecastDefaults;
  initial: { request: SimulateRequest; data: SimulateResponse } | null;
}) {
  const totalLaps = stints.total_laps;
  const { params, update } = useUrlState();

  // Drivers who finished on dry tyres: the only ones the API can compare against.
  const eligible = useMemo(
    () => event.drivers.filter((d) => actualStints(stints.stints, d.id, totalLaps) && (stints.finish_position[d.id] ?? null) != null),
    [event.drivers, stints, totalLaps],
  );
  const { prefs } = usePreferences();
  const favorite = eligible.find((d) => d.id === prefs.favorite_driver_id)?.code;
  const code = parseDriverCodes(params.get("d") ?? undefined, 1)[0] ?? favorite ?? defaults.driverCode;
  const driver = eligible.find((d) => d.code === code) ?? eligible.find((d) => d.code === defaults.driverCode) ?? eligible[0];
  const safetyCars = parseChoice(params.get("sc") ?? undefined, SC_MODES, defaults.safetyCars.toUpperCase() as "RANDOM").toLowerCase() as SafetyCarMode;

  // Applied strategies come from the URL (shareable); otherwise the page defaults.
  const fromUrl = STRATEGY_KEYS.map((k) => parseStints(params.get(k))).filter((s): s is StintIn[] => s !== null);
  const applied = fromUrl.length ? fromUrl.slice(0, MAX_STRATEGIES) : defaults.strategies;
  const appliedKey = applied.map(encodeStints).join("|");
  const [drafts, setDrafts] = useState<StintIn[][]>(applied);
  const [draftKey, setDraftKey] = useState(appliedKey);
  if (draftKey !== appliedKey) {
    // URL changed (back/forward or a shared link): resync the editor.
    setDraftKey(appliedKey);
    setDrafts(applied);
  }

  const valid = applied.every((s) => strategyErrors(s, totalLaps).length === 0);
  const request =
    driver && valid
      ? buildRequest(
          event.id,
          driver.id,
          applied.map((s, i) => ({ label: strategyLabel(i), stints: s })),
          safetyCars,
        )
      : null;
  const query = useForecast(request, initial ?? undefined);
  const actual = driver ? actualStints(stints.stints, driver.id, totalLaps) : null;

  const draftsValid = drafts.length > 0 && drafts.every((s) => strategyErrors(s, totalLaps).length === 0);
  const dirty = drafts.map(encodeStints).join("|") !== appliedKey;
  const simulate = () =>
    update(Object.fromEntries(STRATEGY_KEYS.map((k, i) => [k, drafts[i] ? encodeStints(drafts[i]) : undefined])));

  if (!driver) {
    return <EmptyState title="No eligible drivers">Nobody finished this race on dry tyres, so there is nothing to compare against.</EmptyState>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <DriverPicker drivers={eligible} selected={[driver.code]} max={1} label="Driver" onChange={(c) => update({ d: c[0] })} />
        <Segmented
          label="Safety cars"
          value={safetyCars === "actual" ? "ACTUAL" : "RANDOM"}
          options={[
            { value: "RANDOM", label: "Random" },
            { value: "ACTUAL", label: "As raced" },
          ]}
          onChange={(v) => update({ sc: v === "ACTUAL" ? "actual" : undefined })}
        />
      </div>

      <section aria-labelledby="builder-title" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="builder-title" className="text-sm font-medium">
            Strategies for {driver.full_name}
            {actual && <span className="font-normal text-subtle"> · real: {describeStints(actual)}</span>}
          </h2>
        </div>
        <StrategyBuilder strategies={drafts} totalLaps={totalLaps} actual={actual} onChange={setDrafts} />
        <div className="flex items-center gap-3">
          <Button variant="primary" size="sm" disabled={!draftsValid || !dirty} onClick={simulate}>
            Simulate
          </Button>
          <span className="text-xs text-subtle">
            {dirty ? (draftsValid ? "Press Simulate to run 500 races." : "Fix the highlighted strategies first.") : "Showing these strategies."}
          </span>
          <span className="ml-auto">
            <SaveButton kind="strategy" title={`${event.season} ${event.name}: ${driver.code} strategy forecast`} />
          </span>
        </div>
      </section>

      <section aria-labelledby="results-title" aria-busy={query.isFetching} className="flex flex-col gap-4">
        <h2 id="results-title" className="sr-only">
          Forecast
        </h2>
        <div className={query.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
          {!request ? (
            <EmptyState title="Nothing to simulate yet">Build up to three strategies that cover all {totalLaps} laps.</EmptyState>
          ) : query.isPending ? (
            <ForecastSkeleton />
          ) : query.isError ? (
            <ForecastError error={query.error} onRetry={() => query.refetch()} />
          ) : (
            <Results data={query.data} />
          )}
        </div>
      </section>

      <ModelNotes model={model} />
    </div>
  );
}

function describeStints(stints: StintIn[]): string {
  return stints.map((s) => `${s.compound[0]}${s.compound.slice(1).toLowerCase()} ${s.laps}`).join(" → ");
}

function Results({ data }: { data: SimulateResponse }) {
  return (
    <div className="flex flex-col gap-6">
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.strategies.map((s, k) => (
          <li key={k} className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: STRATEGY_COLORS[k] }} />
              {s.label}
              <StintChips stints={s.stints} />
            </div>
            <p className="text-2xl font-semibold tracking-tight">{formatDelta(s.finish_delta_s.p50)}</p>
            <p className="text-xs text-muted">
              than the real strategy (median). In 90% of races: {formatDelta(s.finish_delta_s.p5)} to {formatDelta(s.finish_delta_s.p95)}.
            </p>
            {s.p_gain != null && (
              <p className="text-xs text-muted">
                Finishes ahead of P{data.actual.model_position}: <span className="font-medium text-fg">{pct(s.p_gain)}</span> · behind:{" "}
                <span className="font-medium text-fg">{pct(s.p_lose)}</span>
              </p>
            )}
          </li>
        ))}
      </ul>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">Gap to the real strategy, lap by lap</h3>
        <p className="text-xs text-subtle">
          Above zero = ahead of what {data.driver.full_name} actually did. Bands cover 80% (light) and 50% (dark) of{" "}
          {data.runs} simulated races; dotted lines mark the real pit stops.
        </p>
        <FanChart data={data} />
      </div>

      {data.actual.model_position != null && data.strategies.some((s) => s.positions) && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">Where {data.driver.code} would have finished</h3>
          <p className="text-xs text-subtle">Rivals keep their real race times; only {data.driver.code}&apos;s strategy changes.</p>
          <FinishDistribution data={data} />
        </div>
      )}
    </div>
  );
}

function StintChips({ stints }: { stints: StintIn[] }) {
  return (
    <span className="ml-auto flex items-center gap-1 text-xs font-normal text-muted">
      {stints.map((s, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          <span
            aria-hidden
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: compoundColor(s.compound), boxShadow: s.compound === "HARD" ? "inset 0 0 0 1px var(--tyre-hard-stroke)" : undefined }}
          />
          <span className="tabular-nums">{s.laps}</span>
        </span>
      ))}
    </span>
  );
}

function ForecastError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  if (error instanceof ApiError && error.status === 429) {
    return (
      <ErrorState
        message={`Too many simulations in a short time. Try again in ${error.retryAfter ?? 60} s.`}
        onRetry={onRetry}
      />
    );
  }
  if (error instanceof ApiError && error.status === 422) {
    return <EmptyState title="Can't simulate this">{error.message}</EmptyState>;
  }
  return <ErrorState message="The simulation didn't finish." onRetry={onRetry} />;
}

function ForecastSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-label="Running simulations">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Skeleton className="h-32" label="Loading forecast" />
        <Skeleton className="h-32" />
        <Skeleton className="hidden h-32 lg:block" />
      </div>
      <Skeleton className="h-[340px]" />
      <p className="text-xs text-subtle">Simulating 500 races. If the API was asleep, the first run can take up to a minute.</p>
    </div>
  );
}

function ModelNotes({ model }: { model: ModelSummary }) {
  const at = (age: number, c: string) => model.curves.find((x) => x.compound === c)?.seconds[age - 1];
  return (
    <details className="rounded-lg border border-border p-4 text-sm">
      <summary className="cursor-pointer font-medium">About this model</summary>
      <div className="mt-3 flex flex-col gap-3 text-muted">
        <p>
          Lap times come from a model fitted on {model.n_races} dry race{model.n_races === 1 ? "" : "s"} at this circuit (2023 onward),
          pulled toward an all-circuit average where data is thin. Each run randomizes safety cars, pit-stop time, lap-to-lap noise
          and how hard the tyres wear on the day.
        </p>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
          <div>
            <dt className="text-xs text-subtle">Pit stop costs</dt>
            <dd className="text-fg">{model.pit_loss.toFixed(1)} s</dd>
          </div>
          <div>
            <dt className="text-xs text-subtle">Safety cars per race</dt>
            <dd className="text-fg">{model.sc_rate.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-xs text-subtle">Lap-to-lap noise</dt>
            <dd className="text-fg">±{model.sigma.toFixed(2)} s</dd>
          </div>
          <div>
            <dt className="text-xs text-subtle">Wear after 15 laps (S/M/H)</dt>
            <dd className="text-fg tabular-nums">
              {["SOFT", "MEDIUM", "HARD"].map((c) => (at(15, c) ?? NaN).toFixed(1)).join(" / ")} s
            </dd>
          </div>
        </dl>
        <p className="text-xs">
          Limits: rivals keep their real race times, cars do not bunch up behind a safety car, and there is no traffic or overtaking
          model. On held-out 2026 races the lap-time model is off by 0.8 s per lap on average, 33% better than assuming constant pace.
        </p>
      </div>
    </details>
  );
}
