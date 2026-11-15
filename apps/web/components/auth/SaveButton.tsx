"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { useAddSaved, useSaved } from "@/lib/queries/me";

import { Button } from "../ui/Button";
import { useAuth } from "./AuthProvider";

/** Save the current view (its URL) to the account; guests are invited to sign in. */
export function SaveButton({ kind, title }: { kind: "chart" | "strategy"; title: string }) {
  const { configured, ready, user } = useAuth();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const path = search ? `${pathname}?${search}` : pathname;
  const saved = useSaved();
  const add = useAddSaved();

  if (!configured || !ready) return null;
  if (!user) {
    return (
      <Link
        href={`/login?next=${encodeURIComponent(path)}`}
        className="inline-flex h-8 items-center rounded-md border border-border px-3 text-sm text-muted hover:text-fg"
      >
        Sign in to save
      </Link>
    );
  }
  const already = saved.data?.some((s) => s.path === path) || add.isSuccess;
  return (
    <Button
      size="sm"
      disabled={already || add.isPending}
      onClick={() => add.mutate({ kind, title: title.slice(0, 120), path })}
      aria-live="polite"
    >
      {already ? "Saved" : add.isPending ? "Saving…" : add.isError ? "Retry save" : "Save"}
    </Button>
  );
}
