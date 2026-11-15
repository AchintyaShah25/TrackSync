"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import type { SimulateResponse } from "@/lib/api/types";
import { STRATEGY_COLORS } from "@/lib/charts/forecast";

import { TooltipBox } from "./ChartTooltip";

interface Row {
  position: number;
  [key: string]: number;
}

/** Probability of each finishing position per strategy (rivals keep their real race times). */
export function finishRows(data: SimulateResponse): Row[] {
  const positions = new Set<number>();
  if (data.actual.model_position) positions.add(data.actual.model_position);
  data.strategies.forEach((s) => s.positions?.forEach((p) => positions.add(p.position)));
  const sorted = [...positions].sort((a, b) => a - b);
  if (!sorted.length) return [];
  const rows: Row[] = [];
  for (let pos = sorted[0]; pos <= sorted[sorted.length - 1]; pos++) {
    const row: Row = { position: pos };
    data.strategies.forEach((s, k) => {
      row[`s${k}`] = s.positions?.find((p) => p.position === pos)?.p ?? 0;
    });
    rows.push(row);
  }
  return rows;
}

export function FinishDistribution({ data }: { data: SimulateResponse }) {
  const rows = useMemo(() => finishRows(data), [data]);
  const actual = data.actual.model_position;
  const summary = `Finishing position odds per strategy; the real result was P${actual}.`;
  return (
    <figure aria-label={summary} className="flex flex-col gap-2">
      <figcaption className="sr-only">{summary}</figcaption>
      <div style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 22, right: 8, bottom: 0, left: -6 }} barGap={1} barCategoryGap="18%">
            <CartesianGrid vertical={false} />
            <XAxis dataKey="position" tick={{ fontSize: 11 }} tickLine={false} tickFormatter={(v: number) => `P${v}`} />
            <YAxis
              width={48}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              domain={[0, 1]}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            />
            {actual && (
              <ReferenceLine
                x={actual}
                stroke="var(--chart-axis)"
                strokeDasharray="3 3"
                label={{ value: "Real", position: "top", fontSize: 11, fill: "var(--chart-text)" }}
              />
            )}
            <Tooltip
              cursor={{ fill: "var(--chart-grid)" }}
              content={(props) => <PositionTooltip {...props} data={data} />}
              isAnimationActive={false}
            />
            {data.strategies.map((s, k) => (
              <Bar key={k} dataKey={`s${k}`} name={s.label} fill={STRATEGY_COLORS[k]} radius={[2, 2, 0, 0]} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

function PositionTooltip({ active, payload, label, data }: TooltipContentProps<ValueType, NameType> & { data: SimulateResponse }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as Row;
  return (
    <TooltipBox>
      <p className="mb-1 font-medium">P{label}</p>
      <ul className="flex flex-col gap-0.5">
        {data.strategies.map((s, k) => (
          <li key={k} className="flex items-center gap-2">
            <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: STRATEGY_COLORS[k] }} />
            <span className="text-muted">{s.label}</span>
            <span className="ml-auto pl-3 font-medium tabular-nums">{Math.round(row[`s${k}`] * 100)}%</span>
          </li>
        ))}
      </ul>
    </TooltipBox>
  );
}
