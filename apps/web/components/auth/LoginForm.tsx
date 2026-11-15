"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { safeNext, supabase } from "@/lib/auth/supabase";

import { Button } from "../ui/Button";

type Status = { kind: "idle" } | { kind: "sending" } | { kind: "sent"; email: string } | { kind: "error"; message: string };

export function LoginForm() {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const sb = supabase();

  if (!sb) {
    return <p className="text-sm text-muted">Sign-in is not available on this deployment.</p>;
  }
  if (status.kind === "sent") {
    return (
      <div role="status" className="rounded-lg border border-border p-4 text-sm">
        <p className="font-medium">Check your inbox</p>
        <p className="mt-1 text-muted">
          We sent a sign-in link to <span className="text-fg">{status.email}</span>. Open it on this device to finish
          signing in.
        </p>
      </div>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setStatus({ kind: "sending" });
    const redirect = `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;
    const { error } = await sb!.auth.signInWithOtp({ email: email.trim(), options: { emailRedirectTo: redirect } });
    if (error) {
      const rateLimited = error.status === 429 || /rate limit/i.test(error.message);
      setStatus({
        kind: "error",
        message: rateLimited
          ? "Too many sign-in emails were sent recently. Try again in an hour."
          : "We could not send the email. Check the address and try again.",
      });
    } else {
      setStatus({ kind: "sent", email: email.trim() });
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label htmlFor="email" className="text-sm font-medium">
        Email
      </label>
      <input
        id="email"
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="h-10 rounded-md border border-border bg-surface px-3 text-sm"
        placeholder="you@example.com"
      />
      <Button type="submit" variant="primary" disabled={status.kind === "sending"}>
        {status.kind === "sending" ? "Sending…" : "Email me a sign-in link"}
      </Button>
      {status.kind === "error" && (
        <p role="alert" className="text-sm text-danger">
          {status.message}
        </p>
      )}
      <p className="text-xs text-subtle">No password. We only use your email to sign you in.</p>
    </form>
  );
}
