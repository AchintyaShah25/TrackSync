import { notFound } from "next/navigation";

import { paths } from "./api/client";
import { serverGetOrNull } from "./api/server";
import type { EventDetail, ResultRow } from "./api/types";
import { eventId } from "./format";

export const FIRST_SEASON = 2023;
export const LAST_SEASON = 2026;

/** Parse /races/[year]/[round] params and load the event, or 404. */
export async function loadEvent(params: Promise<{ year: string; round: string }>) {
  const { year, round } = await params;
  const y = Number(year);
  const r = Number(round);
  if (!Number.isInteger(y) || !Number.isInteger(r) || y < FIRST_SEASON || y > LAST_SEASON || r < 1 || r > 30) {
    notFound();
  }
  const event = await serverGetOrNull<EventDetail>(paths.event(eventId(y, r)));
  if (!event) notFound();
  return event;
}

/** Top-N finishers' codes of a session, used as default chart selections. */
export async function topCodes(event: EventDetail, session: string, n: number): Promise<string[]> {
  const rows = (await serverGetOrNull<ResultRow[]>(paths.results(event.id, session))) ?? [];
  const codes = rows.filter((r) => r.position != null).slice(0, n).map((r) => r.driver.code);
  return codes.length ? codes : event.drivers.slice(0, n).map((d) => d.code);
}
