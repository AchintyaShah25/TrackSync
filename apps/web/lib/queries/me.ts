"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth/AuthProvider";

import { apiDelete, apiGet, apiPost, apiPut, paths } from "../api/client";
import type { Preferences, SavedItem, SavedItemIn } from "../api/types";

export const DEFAULT_PREFERENCES: Preferences = {
  favorite_driver_id: null,
  favorite_team_id: null,
  theme: null,
  units: "metric",
  chat_level: "beginner",
  home_widgets: [],
};

/** The signed-in user's preferences (defaults when signed out or still loading). */
export function usePreferences() {
  const { user, token } = useAuth();
  const query = useQuery({
    queryKey: ["me", user?.id, "preferences"],
    queryFn: async ({ signal }) => apiGet<Preferences>(paths.preferences(), { signal, token: await token() }),
    enabled: !!user,
    staleTime: 5 * 60 * 1000,
  });
  return { ...query, prefs: query.data ?? DEFAULT_PREFERENCES };
}

export function useSavePreferences() {
  const { user, token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (prefs: Preferences) => apiPut<Preferences>(paths.preferences(), prefs, { token: await token() }),
    onSuccess: (data) => qc.setQueryData(["me", user?.id, "preferences"], data),
  });
}

export function useSaved() {
  const { user, token } = useAuth();
  return useQuery({
    queryKey: ["me", user?.id, "saved"],
    queryFn: async ({ signal }) => apiGet<SavedItem[]>(paths.saved(), { signal, token: await token() }),
    enabled: !!user,
    staleTime: 60 * 1000,
  });
}

export function useAddSaved() {
  const { user, token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (item: SavedItemIn) => apiPost<SavedItem>(paths.saved(), item, { token: await token() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me", user?.id, "saved"] }),
  });
}

export function useDeleteSaved() {
  const { user, token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => apiDelete(paths.savedItem(id), { token: await token() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me", user?.id] }),
  });
}
