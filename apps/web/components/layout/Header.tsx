import Link from "next/link";

import { ThemeToggle } from "./ThemeToggle";

const CURRENT_SEASON = 2026;

export function Header() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex h-14 max-w-[var(--content-max)] items-center justify-between px-[var(--gutter)]">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span aria-hidden className="inline-block h-3 w-3 rounded-sm bg-accent" />
          TrackSync
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1 text-sm">
          <Link
            href={`/seasons/${CURRENT_SEASON}`}
            className="rounded-md px-3 py-2 text-muted hover:bg-surface-muted hover:text-fg"
          >
            Seasons
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
