"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { ChatChartSpec } from "@/lib/api/types";
import { STRATEGY_COLORS } from "@/lib/charts/forecast";

import { TooltipBox } from "../charts/ChartTooltip";

const COLORS = [...STRATEGY_COLORS, "var(--chart-secondary-series)"];

/** Rows keyed by x with one column per series, for Recharts. */
export function chartRows(spec: ChatChartSpec): Record<string, number | string>[] {
  const byX = new Map<number | string, Record<string, number | string>>();
  spec.series.forEach((s, k) => {
    for (const [x, y] of s.points) {
      const row = byX.get(x) ?? { x };
      row[`s${k}`] = y;
      byX.set(x, row);
    }
  });
  const rows = [...byX.values()];
  if (spec.type === "line") rows.sort((a, b) => Number(a.x) - Number(b.x));
  return rows;
}

/** Renders a chart the agent made from query results (decision 0029: grounded data only). */
export function ChatChart({ spec }: { spec: ChatChartSpec }) {
  const rows = useMemo(() => chartRows(spec), [spec]);
  const summary = `${spec.title}: ${spec.series.map((s) => s.name).join(", ")}. ${spec.y_label} by ${spec.x_label}.`;
  const reversed = /position/i.test(spec.y_label); // P1 at the top
  const tooltip = (
    <Tooltip
      isAnimationActive={false}
      cursor={{ stroke: "var(--chart-axis)", fill: "var(--chart-grid)" }}
      content={({ active, payload, label }) =>
        active && payload?.length ? (
          <TooltipBox>
            <p className="mb-1 font-medium">
              {spec.x_label} {String(label)}
            </p>
            {payload.map((p) => (
              <p key={String(p.dataKey)} className="flex justify-between gap-3">
                <span className="text-muted">{p.name}</span>
                <span className="font-medium tabular-nums">{String(p.value)}</span>
              </p>
            ))}
          </TooltipBox>
        ) : null
      }
    />
  );
  return (
    <figure aria-label={summary} className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <figcaption className="text-sm font-medium">{spec.title}</figcaption>
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          {spec.type === "bar" ? (
            <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" tick={{ fontSize: 11 }} tickLine={false} interval={0} />
              <YAxis width={44} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              {tooltip}
              {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
              {spec.series.map((s, k) => (
                <Bar key={k} dataKey={`s${k}`} name={s.name} fill={COLORS[k % COLORS.length]} radius={[2, 2, 0, 0]} isAnimationActive={false} />
              ))}
            </BarChart>
          ) : (
            <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} allowDecimals={false} tick={{ fontSize: 11 }} tickLine={false} />
              <YAxis width={44} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} reversed={reversed} allowDecimals={!reversed} domain={["auto", "auto"]} />
              {tooltip}
              {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
              {spec.series.map((s, k) => (
                <Line key={k} dataKey={`s${k}`} name={s.name} stroke={COLORS[k % COLORS.length]} strokeWidth={2} dot={rows.length < 30} connectNulls isAnimationActive={false} />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-subtle">
        {spec.y_label} by {spec.x_label}, from TrackSync data.
      </p>
    </figure>
  );
}
