import Link from "next/link";

import { RaceTabs } from "@/components/race/RaceTabs";
import { loadEvent } from "@/lib/race";

export default async function RaceLayout({ children, params }: LayoutProps<"/races/[year]/[round]">) {
  const event = await loadEvent(params);
  const date = event.race_start_utc
    ? new Intl.DateTimeFormat("en", { dateStyle: "long", timeZone: "UTC" }).format(new Date(event.race_start_utc))
    : null;
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-sm text-muted">
          <Link href={`/seasons/${event.season}`} className="hover:text-fg">
            {event.season}
          </Link>{" "}
          · Round {event.round}
          {event.format === "sprint" && " · Sprint weekend"}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{event.name}</h1>
        <p className="mt-1 text-sm text-muted">
          {event.circuit_name}
          {event.locality ? `, ${event.locality}` : ""}
          {date ? ` · ${date}` : ""}
        </p>
      </div>
      <RaceTabs base={`/races/${event.season}/${event.round}`} />
      {children}
    </div>
  );
}
