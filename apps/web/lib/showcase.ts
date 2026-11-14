// The static showcase: example analyses featured on the landing page. Their pages are
// generated at build time with these exact selections so they load instantly even while
// the free API sleeps (CLAUDE.md rule 5). Open decision in SPEC §9; easy to swap.

export interface ShowcaseExample {
  title: string;
  blurb: string;
  season: number;
  round: number;
  view: "telemetry" | "strategy" | "track";
  session: "Q" | "R";
  drivers: string[]; // codes; telemetry uses two, track uses one
}

export const SHOWCASE: ShowcaseExample[] = [
  {
    title: "Verstappen vs Norris at Monza",
    blurb: "Qualifying telemetry on the fastest track of the year: braking points and top speed.",
    season: 2024,
    round: 16,
    view: "telemetry",
    session: "Q",
    drivers: ["VER", "NOR"],
  },
  {
    title: "Strategy chaos in São Paulo",
    blurb: "A wet race, a red flag and a safety car: every stint of the 2024 São Paulo GP.",
    season: 2024,
    round: 21,
    view: "strategy",
    session: "R",
    drivers: [],
  },
  {
    title: "Monaco, colored by speed",
    blurb: "Pole lap around the slowest circuit on the calendar, from hairpin to tunnel.",
    season: 2025,
    round: 8,
    view: "track",
    session: "Q",
    drivers: [],
  },
  {
    title: "Brazil 2026: the latest race",
    blurb: "Tire strategies from the most recent Grand Prix in our data.",
    season: 2026,
    round: 20,
    view: "strategy",
    session: "R",
    drivers: [],
  },
];

export const showcaseHref = (e: ShowcaseExample) => {
  const q = new URLSearchParams({ session: e.session });
  if (e.drivers.length) q.set(e.view === "track" ? "driver" : "drivers", e.drivers.join(","));
  return `/races/${e.season}/${e.round}/${e.view}?${q.toString()}`;
};

/** Preset selection for a race view, if that view is a showcase example. */
export function showcasePreset(season: number, round: number, view: ShowcaseExample["view"]) {
  return SHOWCASE.find((e) => e.season === season && e.round === round && e.view === view);
}
