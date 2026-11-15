"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import type { Trace } from "@/lib/api/types";
import { seriesStyles } from "@/lib/charts/series";
import { mergeTraces, summarizeTrace, type Channel } from "@/lib/charts/telemetry";
import { formatLapTime } from "@/lib/format";

import { TooltipBox } from "./ChartTooltip";

const PANELS: { channel: Channel; label: string; unit: string; height: number; step?: boolean; domain: [number | "auto", number | "auto"] }[] = [
  { channel: "speed", label: "Speed", unit: "km/h", height: 220, domain: ["auto", "auto"] },
  { channel: "throttle", label: "Throttle", unit: "%", height: 110, domain: [0, 100] },
  { channel: "brake", label: "Brake", unit: "", height: 70, step: true, domain: [0, 1] },
  { channel: "gear", label: "Gear", unit: "", height: 110, step: true, domain: [1, 8] },
];

const km = (m: number) => `${(m / 1000).toFixed(1)} km`;

export function TelemetryChart({ traces }: { traces: Trace[] }) {
  const rows = useMemo(() => mergeTraces(traces), [traces]);
  const styles = useMemo(() => seriesStyles(traces.map((t) => t.driver)), [traces]);
  const summary = useMemo(() => describe(traces), [traces]);

  return (
    <figure aria-label={summary} className="flex flex-col gap-2">
      <figcaption className="sr-only">{summary}</figcaption>
      {PANELS.map((panel, i) => (
        <div key={panel.channel}>
          <div className="mb-1 flex items-baseline justify-between text-xs text-muted">
            <span className="font-medium text-fg">{panel.label}</span>
            {panel.unit && <span>{panel.unit}</span>}
          </div>
          <div style={{ height: panel.height }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} syncId="telemetry" margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
                <CartesianGrid vertical={false} strokeDasharray="0" />
                <XAxis
                  dataKey="d"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={km}
                  hide={i < PANELS.length - 1}
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                />
                <YAxis
                  domain={panel.domain}
                  width={44}
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                  ticks={panel.channel === "brake" ? [0, 1] : panel.channel === "gear" ? [2, 4, 6, 8] : undefined}
                  tickFormatter={panel.channel === "brake" ? (v: number) => (v ? "On" : "Off") : undefined}
                />
                <Tooltip
                  cursor={{ stroke: "var(--chart-axis)", strokeWidth: 1 }}
                  content={(props) => <TelemetryTooltip {...props} traces={traces} channel={panel.channel} />}
                  isAnimationActive={false}
                />
                {traces.map((t) => {
                  const s = styles.get(t.driver.id)!;
                  return (
                    <Line
                      key={t.driver.id}
                      dataKey={`${t.driver.id}:${panel.channel}`}
                      name={t.driver.code}
                      type={panel.step ? "stepAfter" : "monotone"}
                      stroke={s.color}
                      strokeWidth={1.75}
                      strokeDasharray={s.dashed ? "5 3" : undefined}
                      dot={false}
                      activeDot={{ r: 3 }}
                      isAnimationActive={false}
                    />
                  );
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ))}
    </figure>
  );
}

function TelemetryTooltip({
  active,
  payload,
  label,
  traces,
  channel,
}: TooltipContentProps<ValueType, NameType> & { traces: Trace[]; channel: Channel }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as Record<string, number>;
  return (
    <TooltipBox>
      <p className="mb-1 text-subtle">{km(Number(label))}</p>
      {traces.map((t) => (
        <p key={t.driver.id} className="flex justify-between gap-4">
          <span className="font-medium">{t.driver.code}</span>
          <span>
            {Math.round(row[`${t.driver.id}:speed`])} km/h · {row[`${t.driver.id}:throttle`]}% · G
            {row[`${t.driver.id}:gear`]}
            {row[`${t.driver.id}:brake`] ? " · brake" : ""}
          </span>
        </p>
      ))}
      <span className="sr-only">{channel}</span>
    </TooltipBox>
  );
}

function describe(traces: Trace[]): string {
  if (!traces.length) return "No telemetry selected.";
  const parts = traces.map((t) => {
    const s = summarizeTrace(t);
    return `${t.driver.full_name}: lap ${formatLapTime(t.lap_time_ms)}, top speed ${s.topSpeed} km/h, full throttle ${s.fullThrottlePct}% of the lap, ${s.brakingZones} braking zones`;
  });
  return `Telemetry comparison over one lap. ${parts.join(". ")}.`;
}
