"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiGet, paths } from "../api/client";
import type { StrategyResponse, TracesResponse } from "../api/types";

export function useTraces(
  eventId: number,
  session: string,
  codes: string[],
  initial?: { session: string; codes: string[]; data: TracesResponse },
) {
  const key = [...codes].sort().join(",");
  const matchesInitial =
    initial && initial.session === session && [...initial.codes].sort().join(",") === key;
  return useQuery({
    queryKey: ["traces", eventId, session, key],
    queryFn: ({ signal }) => apiGet<TracesResponse>(paths.traces(eventId, codes, session), { signal }),
    enabled: codes.length > 0,
    initialData: matchesInitial ? initial.data : undefined,
    placeholderData: keepPreviousData,
  });
}

export function useStrategy(eventId: number, session: string, initial?: StrategyResponse) {
  return useQuery({
    queryKey: ["stints", eventId, session],
    queryFn: ({ signal }) => apiGet<StrategyResponse>(paths.stints(eventId, session), { signal }),
    initialData: initial && initial.session === session ? initial : undefined,
    placeholderData: keepPreviousData,
  });
}
