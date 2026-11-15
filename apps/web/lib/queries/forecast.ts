"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiGet, apiPost, ApiError, paths } from "../api/client";
import type { ModelSummary, SimulateRequest, SimulateResponse } from "../api/types";

/**
 * Runs a simulation for `request` (null = nothing to run yet). Keyed on the full request with
 * a fixed seed, so the same strategies hit the cache instead of the rate-limited API.
 */
export function useForecast(request: SimulateRequest | null, initial?: { request: SimulateRequest; data: SimulateResponse }) {
  const key = request ? JSON.stringify(request) : "";
  return useQuery({
    queryKey: ["forecast", key],
    queryFn: ({ signal }) => apiPost<SimulateResponse>(paths.simulate(), request, { signal, timeoutMs: 60_000 }),
    enabled: request !== null,
    initialData: initial && JSON.stringify(initial.request) === key ? initial.data : undefined,
    placeholderData: keepPreviousData,
    staleTime: Infinity, // deterministic for a request: never refetch
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
  });
}

export function useModelSummary(circuitId: string, initial: ModelSummary | null) {
  return useQuery({
    queryKey: ["model", circuitId],
    queryFn: ({ signal }) => apiGet<ModelSummary>(paths.modelParams(circuitId), { signal }),
    initialData: initial ?? undefined,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });
}
