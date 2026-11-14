"use client";

import { useMemo } from "react";

import type { Circuit, Trace } from "@/lib/api/types";
import { SPEED_LEGEND_STOPS, speedColor, speedDomain } from "@/lib/charts/speedScale";
import { formatLapTime } from "@/lib/format";

// Hand-rolled SVG (decision 0011): per-segment colors are awkward in Recharts.
// Outline, trace and corners share the normalized frame built by the ETL (decision 0007).
const PAD = 0.06;
const LABEL_OFFSET = 0.035;

export function TrackMap({ trace, circuit }: { trace: Trace; circuit: Circuit | null }) {
  const { x, y, speed, d } = trace.points;
  const [vmin, vmax] = useMemo(() => speedDomain(speed), [speed]);

  const box = useMemo(() => {
    const xs = [...x, ...(circuit?.outline?.x ?? [])];
    const ys = [...y, ...(circuit?.outline?.y ?? [])];
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    return { minX: minX - PAD, minY: minY - PAD, w: maxX - minX + 2 * PAD, h: maxY - minY + 2 * PAD, maxY };
  }, [x, y, circuit]);

  // SVG y grows downward; flip so the map matches the official orientation.
  const fy = (v: number) => box.maxY - v + box.minY;

  const segments = useMemo(
    () =>
      x.slice(0, -1).map((_, i) => ({
        x1: x[i], y1: fy(y[i]), x2: x[i + 1], y2: fy(y[i + 1]),
        color: speedColor((speed[i] - vmin) / Math.max(vmax - vmin, 1)),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [x, y, speed, vmin, vmax, box],
  );

  const outlinePath = useMemo(() => {
    const o = circuit?.outline;
    if (!o?.x.length) return null;
    return o.x.map((px, i) => `${i ? "L" : "M"}${px.toFixed(4)},${fy(o.y[i]).toFixed(4)}`).join("") + "Z";
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [circuit, box]);

  const slowest = speed.indexOf(vmin);
  const summary = `Track map of ${circuit?.name ?? "the circuit"} colored by ${trace.driver.full_name}'s speed on a ${formatLapTime(
    trace.lap_time_ms,
  )} lap: from ${Math.round(vmin)} km/h (slowest, ${(d[slowest] / 1000).toFixed(1)} km into the lap) to ${Math.round(vmax)} km/h.`;

  const stroke = box.w * 0.012;

  return (
    <figure className="flex flex-col gap-4">
      <svg
        role="img"
        aria-label={summary}
        viewBox={`${box.minX} ${box.minY} ${box.w} ${box.h}`}
        className="mx-auto h-auto max-h-[70vh] w-full"
      >
        {outlinePath && (
          <path d={outlinePath} fill="none" stroke="var(--color-border-strong)" strokeWidth={stroke * 2.4} strokeLinejoin="round" />
        )}
        {segments.map((s, i) => (
          <line key={i} {...s} stroke={s.color} strokeWidth={stroke} strokeLinecap="round" />
        ))}
        <circle cx={x[0]} cy={fy(y[0])} r={stroke * 1.1} fill="var(--color-text)" />
        {circuit?.corners.map((c) => {
          const a = (c.angle * Math.PI) / 180;
          const lx = c.x + Math.cos(a) * LABEL_OFFSET;
          const ly = fy(c.y + Math.sin(a) * LABEL_OFFSET);
          return (
            <text
              key={`${c.number}${c.letter}`}
              x={lx}
              y={ly}
              fontSize={box.w * 0.022}
              textAnchor="middle"
              dominantBaseline="central"
              fill="var(--color-text-muted)"
            >
              {c.number}
              {c.letter}
            </text>
          );
        })}
      </svg>
      <figcaption className="flex flex-col gap-2 text-xs text-muted">
        <div className="flex items-center gap-3">
          <span>{Math.round(vmin)} km/h</span>
          <span
            aria-hidden
            className="h-2 flex-1 rounded-full"
            style={{ background: `linear-gradient(to right, ${SPEED_LEGEND_STOPS.map((s) => s.color).join(", ")})` }}
          />
          <span>{Math.round(vmax)} km/h</span>
        </div>
        <p>Dot marks the start/finish line. Numbers are corners.</p>
      </figcaption>
    </figure>
  );
}
