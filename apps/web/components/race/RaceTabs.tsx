"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "../ui/cn";

const TABS = [
  { slug: "", label: "Results" },
  { slug: "telemetry", label: "Telemetry" },
  { slug: "strategy", label: "Strategy" },
  { slug: "track", label: "Track map" },
];

export function RaceTabs({ base }: { base: string }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Race views" className="-mx-[var(--gutter)] overflow-x-auto px-[var(--gutter)]">
      <ul className="flex gap-1 border-b border-border">
        {TABS.map((t) => {
          const href = t.slug ? `${base}/${t.slug}` : base;
          const active = pathname === href;
          return (
            <li key={t.label}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "-mb-px inline-block whitespace-nowrap border-b-2 px-3 py-2 text-sm",
                  active ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg",
                )}
              >
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
