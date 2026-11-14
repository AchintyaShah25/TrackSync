"use client";

import { useEffect, useState } from "react";

import type { EventSummary } from "@/lib/api/types";
import { countdown, formatLocalStart, nextRace } from "@/lib/schedule";

/**
 * Next-race countdown in the viewer's local time. The full remaining schedule is embedded
 * at build time; the client picks the next race, so the static page never goes stale.
 */
export function Countdown({ events }: { events: EventSummary[] }) {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const tick = () => setNow(new Date());
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  const race = now ? nextRace(events, now) : null;
  if (now && !race) {
    return <p className="text-sm text-muted">The season is over. See you next year.</p>;
  }
  const c = race && now ? countdown(new Date(race.race_start_utc!), now) : null;
  const units = c
    ? [
        ["days", c.days],
        ["hrs", c.hours],
        ["min", c.minutes],
        ["sec", c.seconds],
      ]
    : [
        ["days", "–"],
        ["hrs", "–"],
        ["min", "–"],
        ["sec", "–"],
      ];

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted">
        Next race{race ? <>: <span className="font-medium text-fg">{race.name}</span></> : null}
      </p>
      <div className="flex gap-3" aria-live="off">
        {units.map(([label, value]) => (
          <div key={label as string} className="min-w-16 rounded-md border border-border bg-surface px-3 py-2 text-center">
            <div className="text-2xl font-semibold tabular-nums">{value}</div>
            <div className="text-xs text-subtle">{label}</div>
          </div>
        ))}
      </div>
      {race && (
        <p className="text-sm text-muted" suppressHydrationWarning>
          Lights out {formatLocalStart(race.race_start_utc!)} (your time)
        </p>
      )}
    </div>
  );
}
