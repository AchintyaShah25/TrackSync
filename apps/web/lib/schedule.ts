import type { EventSummary } from "./api/types";

/** The first event whose race has not started yet, relative to `now`. */
export function nextRace(events: EventSummary[], now: Date): EventSummary | null {
  return (
    events
      .filter((e) => e.race_start_utc && new Date(e.race_start_utc).getTime() > now.getTime())
      .sort((a, b) => Date.parse(a.race_start_utc!) - Date.parse(b.race_start_utc!))[0] ?? null
  );
}

export interface Countdown {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  done: boolean;
}

export function countdown(target: Date, now: Date): Countdown {
  const ms = Math.max(target.getTime() - now.getTime(), 0);
  return {
    days: Math.floor(ms / 86_400_000),
    hours: Math.floor((ms % 86_400_000) / 3_600_000),
    minutes: Math.floor((ms % 3_600_000) / 60_000),
    seconds: Math.floor((ms % 60_000) / 1000),
    done: ms === 0,
  };
}

/** Race start in the viewer's own time zone and locale, e.g. "Sun, Nov 22, 5:00 AM GMT+1". */
export function formatLocalStart(iso: string, locale?: string, timeZone?: string): string {
  return new Intl.DateTimeFormat(locale, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
    timeZone,
  }).format(new Date(iso));
}
