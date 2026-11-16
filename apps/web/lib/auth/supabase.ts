"use client";

// Browser-only Supabase Auth (decision 0030). Pages stay static: nothing personal is
// rendered on the server, and the API checks the bearer token on /me and /chat.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null | undefined;

/** The shared browser client, or null when sign-in is not configured (CI, previews). */
export function supabase(): SupabaseClient | null {
  if (client !== undefined) return client;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  client =
    url && key
      ? createClient(url, key, {
          // /auth/callback exchanges the code itself; automatic URL detection would race it
          // and spend the one-time code first, making the callback report a failed link.
          auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
        })
      : null;
  return client;
}

/** Only same-site paths are allowed as post-sign-in destinations (no open redirects). */
export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/";
  return value;
}
