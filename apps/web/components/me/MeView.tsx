"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import type { DriverRef, Preferences } from "@/lib/api/types";
import { useDeleteSaved, usePreferences, useSaved, useSavePreferences } from "@/lib/queries/me";

import { Button } from "../ui/Button";
import { Segmented } from "../ui/Segmented";
import { Skeleton } from "../ui/Skeleton";
import { EmptyState, ErrorState } from "../ui/States";

const MAX_PINNED = 6;

export function MeView({ drivers }: { drivers: DriverRef[] }) {
  const { configured, ready, user, signOut } = useAuth();
  if (!ready) return <Skeleton className="h-64" label="Loading your account" />;
  if (!configured || !user) {
    return (
      <EmptyState title="You're browsing as a guest">
        Everything works without an account.{" "}
        <Link href="/login?next=/me" className="text-accent hover:underline">
          Sign in
        </Link>{" "}
        to save charts and strategies and set a favorite driver.
      </EmptyState>
    );
  }
  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Your account</h1>
          <p className="mt-1 text-sm text-muted">Signed in as {user.email}</p>
        </div>
        <Button size="sm" onClick={() => signOut()}>
          Sign out
        </Button>
      </div>
      <PreferencesForm drivers={drivers} />
      <SavedList />
    </div>
  );
}

function PreferencesForm({ drivers }: { drivers: DriverRef[] }) {
  const { prefs, isPending, isError, refetch } = usePreferences();
  const save = useSavePreferences();
  if (isPending) return <Skeleton className="h-48" label="Loading preferences" />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;
  const update = (patch: Partial<Preferences>) => save.mutate({ ...prefs, ...patch });
  return (
    <section aria-labelledby="prefs" className="flex flex-col gap-5">
      <h2 id="prefs" className="text-lg font-semibold tracking-tight">
        Preferences
      </h2>
      <label className="flex max-w-xs flex-col gap-1.5 text-sm">
        <span className="text-xs text-subtle">Favorite driver (preselected in charts)</span>
        <select
          value={prefs.favorite_driver_id ?? ""}
          onChange={(e) => update({ favorite_driver_id: e.target.value || null })}
          className="h-9 rounded-md border border-border bg-surface px-2"
        >
          <option value="">None</option>
          {drivers.map((d) => (
            <option key={d.id} value={d.id}>
              {d.full_name}
            </option>
          ))}
        </select>
      </label>
      <div className="flex flex-col gap-1.5">
        <span className="text-xs text-subtle">Speed units</span>
        <Segmented
          label="Speed units"
          value={prefs.units}
          options={[
            { value: "metric", label: "km/h" },
            { value: "imperial", label: "mph" },
          ]}
          onChange={(units) => update({ units })}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-xs text-subtle">Chat answers</span>
        <Segmented
          label="Chat answer level"
          value={prefs.chat_level}
          options={[
            { value: "beginner", label: "Explain the basics" },
            { value: "expert", label: "Expert" },
          ]}
          onChange={(chat_level) => update({ chat_level })}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-xs text-subtle">Theme on every device</span>
        <Segmented
          label="Theme"
          value={prefs.theme ?? "system"}
          options={[
            { value: "system", label: "System" },
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
          ]}
          onChange={(theme) => update({ theme })}
        />
      </div>
      <p className="text-xs text-subtle" aria-live="polite">
        {save.isPending ? "Saving…" : save.isError ? "Could not save. Try again." : save.isSuccess ? "Saved." : " "}
      </p>
    </section>
  );
}

function SavedList() {
  const saved = useSaved();
  const { prefs } = usePreferences();
  const save = useSavePreferences();
  const del = useDeleteSaved();
  const [error, setError] = useState<string | null>(null);
  const pinned = new Set(prefs.home_widgets);

  function togglePin(id: string) {
    const next = pinned.has(id) ? prefs.home_widgets.filter((x) => x !== id) : [...prefs.home_widgets, id];
    if (next.length > MAX_PINNED) {
      setError(`You can pin up to ${MAX_PINNED} items to the home page.`);
      return;
    }
    setError(null);
    save.mutate({ ...prefs, home_widgets: next });
  }

  return (
    <section aria-labelledby="saved" className="flex flex-col gap-4">
      <h2 id="saved" className="text-lg font-semibold tracking-tight">
        Saved
      </h2>
      {saved.isPending ? (
        <Skeleton className="h-32" label="Loading saved items" />
      ) : saved.isError ? (
        <ErrorState onRetry={() => saved.refetch()} />
      ) : saved.data.length === 0 ? (
        <EmptyState title="Nothing saved yet">
          Use the Save button on telemetry, strategy, forecast and track views to keep them here.
        </EmptyState>
      ) : (
        <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
          {saved.data.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <Link href={s.path} className="min-w-0 flex-1 truncate font-medium hover:text-accent">
                {s.title}
              </Link>
              <span className="flex items-center gap-1">
                <Button size="sm" variant="ghost" aria-pressed={pinned.has(s.id)} onClick={() => togglePin(s.id)}>
                  {pinned.has(s.id) ? "Unpin" : "Pin to home"}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => del.mutate(s.id)} aria-label={`Delete ${s.title}`}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </section>
  );
}
