"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import type { StrategyResponse } from "@/lib/api/types";
import {
  COMPOUNDS,
  compoundColor,
  compoundLabel,
  strategyRows,
  typicalStops,
  type StrategyRow,
} from "@/lib/charts/strategy";

import { TooltipBox } from "./ChartTooltip";

const ROW_HEIGHT = 26;

type Datum = { label: string; row: StrategyRow } & Record<string, number | string | StrategyRow>;

export function StrategyChart({ data }: { data: StrategyResponse }) {
  const rows = useMemo(() => strategyRows(data), [data]);
  const maxStints = Math.max(1, ...rows.map((r) => r.stints.length));
  const chartData: Datum[] = useMemo(
    () =>
      rows.map((r) => {
        const d: Datum = { label: `${r.position ?? "–"}  ${r.driver.code}`, row: r };
        r.stints.forEach((s, i) => {
          d[`s${i}`] = s.laps;
        });
        return d;
      }),
    [rows],
  );
  const used = COMPOUNDS.filter((c) => data.stints.some((s) => (s.compound ?? "").toUpperCase() === c));
  const stops = typicalStops(rows);
  const summary = `Tire strategy for ${rows.length} drivers over ${data.total_laps} laps. ${
    stops === null ? "" : `Most drivers made ${stops} stop${stops === 1 ? "" : "s"}. `
  }Compounds used: ${used.map((c) => compoundLabel(c)).join(", ") || "unknown"}.`;

  return (
    <figure aria-label={summary} className="flex flex-col gap-3">
      <figcaption className="sr-only">{summary}</figcaption>
      <Legend compounds={used} />
      <div style={{ height: rows.length * ROW_HEIGHT + 40 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" barCategoryGap={4} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid horizontal={false} />
            <XAxis
              type="number"
              domain={[0, data.total_laps]}
              allowDecimals={false}
              tick={{ fontSize: 11 }}
              tickLine={false}
              label={{ value: "Lap", position: "insideBottomRight", offset: -2, fontSize: 11 }}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={64}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              interval={0}
            />
            <Tooltip
              cursor={{ fill: "var(--color-surface-muted)" }}
              content={(props) => <StrategyTooltip {...props} />}
              isAnimationActive={false}
            />
            {Array.from({ length: maxStints }, (_, i) => (
              <Bar key={i} dataKey={`s${i}`} stackId="race" isAnimationActive={false}>
                {chartData.map((d) => {
                  const stint = d.row.stints[i];
                  const hard = (stint?.compound ?? "").toUpperCase() === "HARD";
                  return (
                    <Cell
                      key={d.row.driver.id}
                      fill={compoundColor(stint?.compound ?? null)}
                      stroke={hard ? "var(--tyre-hard-stroke)" : "var(--color-surface)"}
                      strokeWidth={1}
                    />
                  );
                })}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

function Legend({ compounds }: { compounds: string[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Compounds">
      {compounds.map((c) => (
        <li key={c} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full border"
            style={{ background: compoundColor(c), borderColor: c === "HARD" ? "var(--tyre-hard-stroke)" : "transparent" }}
          />
          {compoundLabel(c)}
        </li>
      ))}
    </ul>
  );
}

function StrategyTooltip({ active, payload }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  const row = (payload[0].payload as Datum).row;
  return (
    <TooltipBox>
      <p className="mb-1 font-medium">
        {row.driver.full_name} · {row.position ? `P${row.position}` : "not classified"} · {row.stops} stop
        {row.stops === 1 ? "" : "s"}
      </p>
      {row.stints.map((s) => (
        <p key={s.stint} className="text-muted">
          Stint {s.stint}: {compoundLabel(s.compound)}, laps {s.start + 1}–{s.start + s.laps}
        </p>
      ))}
    </TooltipBox>
  );
}
