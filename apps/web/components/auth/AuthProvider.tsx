"use client";

import type { Session, User } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { supabase } from "@/lib/auth/supabase";

interface AuthState {
  /** Sign-in is configured for this deployment. */
  configured: boolean;
  /** The initial session check has finished. */
  ready: boolean;
  user: User | null;
  /** Fresh access token for API calls, or undefined when signed out. */
  token: () => Promise<string | undefined>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  configured: false,
  ready: true,
  user: null,
  token: async () => undefined,
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const sb = supabase();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(sb === null);

  useEffect(() => {
    if (!sb) return;
    let alive = true;
    sb.auth.getSession().then(({ data }) => {
      if (!alive) return;
      setSession(data.session);
      setReady(true);
    });
    const { data } = sb.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => {
      alive = false;
      data.subscription.unsubscribe();
    };
  }, [sb]);

  const token = useCallback(async () => {
    if (!sb) return undefined;
    const { data } = await sb.auth.getSession(); // refreshes an expiring token
    return data.session?.access_token;
  }, [sb]);

  const signOut = useCallback(async () => {
    await sb?.auth.signOut();
  }, [sb]);

  const value = useMemo(
    () => ({ configured: sb !== null, ready, user: session?.user ?? null, token, signOut }),
    [sb, ready, session, token, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
