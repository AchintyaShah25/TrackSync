"use client";

import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import type { SimulateResponse } from "@/lib/api/types";
import {
  BAND_INNER_OPACITY,
  BAND_OUTER_OPACITY,
  describeForecast,
  fanRows,
  STRATEGY_COLORS,
  type FanRow,
} from "@/lib/charts/forecast";

import { TooltipBox } from "./ChartTooltip";

const signed = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(Math.abs(v) < 10 ? 1 : 0)}s`;

/** Laps (1-based, inclusive ranges) that were neutralized in the real race. */
function neutralRuns(rows: FanRow[]): [number, number][] {
  const runs: [number, number][] = [];
  for (const r of rows) {
    if ((r.sc ?? 0) < 0.5) continue;
    const last = runs.at(-1);
    if (last && last[1] === r.lap - 1) last[1] = r.lap;
    else runs.push([r.lap, r.lap]);
  }
  return runs;
}

/**
 * The outcome fan chart (SPEC M2 signature visual): for each strategy, how far ahead (+) or
 * behind (−) of the driver's real strategy it runs, lap by lap, across all simulated races.
 * Light band = 80% of races, dark band = middle 50%, line = median.
 */
export function FanChart({ data, height = 340 }: { data: SimulateResponse; height?: number }) {
  const rows = useMemo(() => fanRows(data), [data]);
  const summary = useMemo(() => describeForecast(data), [data]);
  const replay = data.safety_cars === "actual";
  const neutral = useMemo(() => (replay ? neutralRuns(rows) : []), [replay, rows]);

  return (
    <figure aria-label={summary} className="flex flex-col gap-2">
      <figcaption className="sr-only">{summary}</figcaption>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="lap"
              type="number"
              domain={[1, data.total_laps]}
              allowDecimals={false}
              tick={{ fontSize: 11 }}
              tickLine={false}
              tickFormatter={(v: number) => `L${v}`}
            />
            <YAxis width={52} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={signed} />
            {!replay && <YAxis yAxisId="sc" hide domain={[0, 4]} />}
            {neutral.map(([a, b]) => (
              <ReferenceArea key={a} x1={a - 0.5} x2={b + 0.5} fill="var(--chart-neutral-band)" fillOpacity={0.14} ifOverflow="hidden" />
            ))}
            {!replay && (
              <Area
                yAxisId="sc"
                dataKey="sc"
                type="step"
                stroke="none"
                fill="var(--chart-neutral-band)"
                fillOpacity={0.18}
                isAnimationActive={false}
                activeDot={false}
              />
            )}
            {data.actual.stop_laps.map((lap) => (
              <ReferenceLine key={`stop-${lap}`} x={lap} stroke="var(--chart-axis)" strokeDasharray="2 4" strokeOpacity={0.6} />
            ))}
            <ReferenceLine y={0} stroke="var(--chart-axis)" strokeWidth={1.5} />
            {data.strategies.map((s, k) => (
              <Area
                key={`o${k}`}
                dataKey={`s${k}_outer`}
                stroke="none"
                fill={STRATEGY_COLORS[k]}
                fillOpacity={BAND_OUTER_OPACITY}
                isAnimationActive={false}
                activeDot={false}
              />
            ))}
            {data.strategies.map((s, k) => (
              <Area
                key={`i${k}`}
                dataKey={`s${k}_inner`}
                stroke="none"
                fill={STRATEGY_COLORS[k]}
                fillOpacity={BAND_INNER_OPACITY}
                isAnimationActive={false}
                activeDot={false}
              />
            ))}
            {data.strategies.map((s, k) => (
              <Line
                key={`m${k}`}
                dataKey={`s${k}_mid`}
                name={s.label}
                stroke={STRATEGY_COLORS[k]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
            <Tooltip
              cursor={{ stroke: "var(--chart-axis)", strokeWidth: 1 }}
              content={(props) => <FanTooltip {...props} data={data} replay={replay} />}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <FanLegend data={data} replay={replay} />
    </figure>
  );
}

function FanTooltip({
  active,
  payload,
  label,
  data,
  replay,
}: TooltipContentProps<ValueType, NameType> & { data: SimulateResponse; replay: boolean }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as FanRow;
  return (
    <TooltipBox>
      <p className="mb-1 font-medium">Lap {label}</p>
      <ul className="flex flex-col gap-0.5">
        {data.strategies.map((s, k) => {
          const inner = row[`s${k}_inner`] as [number, number];
          return (
            <li key={k} className="flex items-center gap-2">
              <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: STRATEGY_COLORS[k] }} />
              <span className="text-muted">{s.label}</span>
              <span className="ml-auto pl-3 font-medium tabular-nums">{signed(row[`s${k}_mid`] as number)}</span>
              <span className="tabular-nums text-subtle">
                ({signed(inner[0])} to {signed(inner[1])})
              </span>
            </li>
          );
        })}
      </ul>
      {(row.sc ?? 0) > 0 && (
        <p className="mt-1 text-subtle">
          {replay ? "Safety car or VSC in the real race" : `SC or VSC in ${Math.round((row.sc ?? 0) * 100)}% of races`}
        </p>
      )}
    </TooltipBox>
  );
}

function FanLegend({ data, replay }: { data: SimulateResponse; replay: boolean }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted">
      {data.strategies.map((s, k) => (
        <li key={k} className="flex items-center gap-1.5">
          <svg aria-hidden width="22" height="10" viewBox="0 0 22 10">
            <rect x="0" y="0" width="22" height="10" fill={STRATEGY_COLORS[k]} fillOpacity={BAND_OUTER_OPACITY} rx="2" />
            <rect x="0" y="2.5" width="22" height="5" fill={STRATEGY_COLORS[k]} fillOpacity={BAND_INNER_OPACITY} />
            <line x1="0" y1="5" x2="22" y2="5" stroke={STRATEGY_COLORS[k]} strokeWidth="2" />
          </svg>
          {s.label}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <svg aria-hidden width="22" height="10" viewBox="0 0 22 10">
          <line x1="0" y1="5" x2="22" y2="5" stroke="var(--chart-axis)" strokeWidth="1.5" />
        </svg>
        Real strategy (0)
      </li>
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="inline-block h-2.5 w-4 rounded-sm" style={{ background: "var(--chart-neutral-band)", opacity: 0.35 }} />
        {replay ? "Safety car / VSC laps" : "Chance of SC / VSC"}
      </li>
    </ul>
  );
}
