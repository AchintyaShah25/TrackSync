"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "./AuthProvider";

const linkClass = "whitespace-nowrap rounded-md px-2 py-2 text-muted hover:bg-surface-muted hover:text-fg sm:px-3";

/** Header sign-in / account link. Hidden when sign-in is not configured. */
export function AccountMenu() {
  const { configured, ready, user } = useAuth();
  const pathname = usePathname();
  if (!configured || !ready) return null;
  if (user) {
    return (
      <Link href="/me" className={linkClass} aria-label={`Your account (${user.email ?? "signed in"})`}>
        Account
      </Link>
    );
  }
  return (
    <Link href={`/login?next=${encodeURIComponent(pathname)}`} className={linkClass}>
      Sign in
    </Link>
  );
}
