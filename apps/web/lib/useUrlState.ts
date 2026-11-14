"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import { withParams } from "./urlState";

/** Read the query string and replace it without scrolling (keeps chart views shareable). */
export function useUrlState() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const update = useCallback(
    (updates: Record<string, string | string[] | undefined>) => {
      router.replace(pathname + withParams(params.toString(), updates), { scroll: false });
    },
    [params, pathname, router],
  );
  return { params, update };
}
