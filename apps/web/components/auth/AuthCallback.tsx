"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { safeNext, supabase } from "@/lib/auth/supabase";

/** Lands from the magic link with ?code=...; the client exchanges it (PKCE) and returns. */
export function AuthCallback() {
  const params = useSearchParams();
  const router = useRouter();
  const code = params.get("code");
  const missing = !supabase() || !code;
  const [exchangeFailed, setExchangeFailed] = useState(false);
  const failed = missing || exchangeFailed;

  useEffect(() => {
    const sb = supabase();
    if (!sb || !code) return;
    const next = safeNext(params.get("next"));
    sb.auth
      .exchangeCodeForSession(code)
      .then(({ error }) => (error ? setExchangeFailed(true) : router.replace(next)))
      .catch(() => setExchangeFailed(true));
  }, [code, params, router]);

  if (failed) {
    return (
      <div className="mx-auto max-w-sm py-8 text-sm">
        <p className="font-medium">That sign-in link did not work</p>
        <p className="mt-1 text-muted">
          Links expire after an hour and work once, in the browser that requested them.{" "}
          <Link href="/login" className="text-accent hover:underline">
            Send a new link
          </Link>
          .
        </p>
      </div>
    );
  }
  return <p className="py-8 text-center text-sm text-muted">Signing you in…</p>;
}
