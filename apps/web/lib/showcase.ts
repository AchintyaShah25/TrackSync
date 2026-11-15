// The static showcase: example analyses featured on the landing page. Their pages are
// generated at build time with these exact selections so they load instantly even while
// the free API sleeps (CLAUDE.md rule 5). Open decision in SPEC §9; easy to swap.

export interface ShowcaseExample {
  title: string;
  blurb: string;
  season: number;
  round: number;
  view: "telemetry" | "strategy" | "track" | "forecast";
  session: "Q" | "R";
  drivers: string[]; // codes; telemetry uses two, track and forecast use one
  /** forecast only: strategies in URL form ("M20-H33") and the safety-car mode. */
  strategies?: string[];
  safetyCars?: "random" | "actual";
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
    title: "Would a one-stop have won Monza for Piastri?",
    blurb: "McLaren stopped twice; Leclerc stopped once and won by 2.7 s. 500 simulated races of Piastri on a one-stop.",
    season: 2024,
    round: 16,
    view: "forecast",
    session: "R",
    drivers: ["PIA"],
    strategies: ["M15-H38", "M21-H32"],
    safetyCars: "actual",
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
  // Forecast defaults are the preset itself, so the bare URL matches the pre-rendered page.
  if (e.view === "forecast") return `/races/${e.season}/${e.round}/forecast`;
  const q = new URLSearchParams({ session: e.session });
  if (e.drivers.length) q.set(e.view === "track" ? "driver" : "drivers", e.drivers.join(","));
  return `/races/${e.season}/${e.round}/${e.view}?${q.toString()}`;
};

/** Preset selection for a race view, if that view is a showcase example. */
export function showcasePreset(season: number, round: number, view: ShowcaseExample["view"]) {
  return SHOWCASE.find((e) => e.season === season && e.round === round && e.view === view);
}
