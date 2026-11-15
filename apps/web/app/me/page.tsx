import type { Metadata } from "next";

import { MeView } from "@/components/me/MeView";
import { paths } from "@/lib/api/client";
import { serverGetOrNull } from "@/lib/api/server";
import type { StandingsResponse } from "@/lib/api/types";
import { LAST_SEASON } from "@/lib/race";

export const metadata: Metadata = { title: "Your account" };
export const revalidate = 86400;

export default async function MePage() {
  // Driver list for the favorite-driver picker: current season standings (static, cached).
  const standings = await serverGetOrNull<StandingsResponse>(paths.standings(LAST_SEASON));
  const drivers = standings?.drivers.map((d) => d.driver) ?? [];
  return <MeView drivers={drivers} />;
}
