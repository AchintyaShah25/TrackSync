"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth/AuthProvider";
import { usePreferences, useSaved } from "@/lib/queries/me";

/** Landing-page section with the signed-in user's pinned saved items. */
export function PinnedItems() {
  const { user } = useAuth();
  const { prefs } = usePreferences();
  const saved = useSaved();
  if (!user || !saved.data) return null;
  const pinned = prefs.home_widgets
    .map((id) => saved.data.find((s) => s.id === id))
    .filter((s): s is NonNullable<typeof s> => !!s);
  if (!pinned.length) return null;
  return (
    <section aria-labelledby="pinned" className="flex flex-col gap-4">
      <h2 id="pinned" className="text-lg font-semibold tracking-tight">
        Your pinned
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {pinned.map((s) => (
          <li key={s.id}>
            <Link
              href={s.path}
              className="flex h-full flex-col gap-1 rounded-lg border border-border bg-surface p-4 hover:border-border-strong"
            >
              <span className="text-xs text-accent">{s.kind === "strategy" ? "Strategy" : "Chart"}</span>
              <span className="font-medium">{s.title}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
