import Link from "next/link";

import { Countdown } from "@/components/race/Countdown";
import { SectionTitle } from "@/components/ui/Card";
import { paths } from "@/lib/api/client";
import { serverGetOrNull } from "@/lib/api/server";
import type { EventSummary } from "@/lib/api/types";
import { LAST_SEASON } from "@/lib/race";
import { SHOWCASE, showcaseHref } from "@/lib/showcase";

// Statically generated and revalidated daily: loads instantly while the API sleeps.
export const revalidate = 86400;

const VIEW_LABEL = {
  telemetry: "Telemetry",
  strategy: "Tire strategy",
  track: "Track map",
  forecast: "Strategy forecast",
} as const;

export default async function Home() {
  const events = (await serverGetOrNull<EventSummary[]>(paths.events(LAST_SEASON))) ?? [];
  const recent = events.filter((e) => e.has_data).slice(-3).reverse();

  return (
    <div className="flex flex-col gap-16">
      <section className="flex flex-col gap-8 pt-4 sm:pt-10 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-xl">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Every lap, every stint, on one screen.
          </h1>
          <p className="mt-4 text-muted">
            Compare drivers&apos; telemetry, follow each car&apos;s tire strategy and see where the
            lap is won, for every Formula 1 race since 2023. No sign-up needed.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href={showcaseHref(SHOWCASE[0])}
              className="inline-flex h-10 items-center rounded-md bg-accent px-4 text-sm font-medium text-accent-fg hover:bg-accent-hover"
            >
              Try a telemetry comparison
            </Link>
            <Link
              href={`/seasons/${LAST_SEASON}`}
              className="inline-flex h-10 items-center rounded-md border border-border px-4 text-sm font-medium hover:bg-surface-muted"
            >
              Browse {LAST_SEASON}
            </Link>
          </div>
        </div>
        <Countdown events={events} />
      </section>

      <section aria-labelledby="examples" className="flex flex-col gap-4">
        <SectionTitle id="examples">Start with an example</SectionTitle>
        <ul className="grid gap-4 sm:grid-cols-2">
          {SHOWCASE.map((e) => (
            <li key={showcaseHref(e)}>
              <Link
                href={showcaseHref(e)}
                className="flex h-full flex-col gap-2 rounded-lg border border-border bg-surface p-5 transition-colors hover:border-border-strong"
              >
                <span className="text-xs text-accent">{VIEW_LABEL[e.view]}</span>
                <span className="font-medium">{e.title}</span>
                <span className="text-sm text-muted">{e.blurb}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {recent.length > 0 && (
        <section aria-labelledby="recent" className="flex flex-col gap-4">
          <SectionTitle id="recent">Recent races</SectionTitle>
          <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
            {recent.map((e) => (
              <li key={e.id}>
                <Link href={`/races/${e.season}/${e.round}`} className="flex items-center justify-between p-4 hover:bg-surface-muted">
                  <span className="font-medium">{e.name}</span>
                  <span className="text-sm text-subtle">Round {e.round}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
