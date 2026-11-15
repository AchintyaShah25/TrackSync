"use client";

import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

import { usePreferences } from "@/lib/queries/me";

/** Applies the saved theme once per sign-in, so it follows the user across devices. */
export function PreferenceEffects() {
  const { prefs, data } = usePreferences();
  const { setTheme } = useTheme();
  const applied = useRef(false);
  useEffect(() => {
    if (data && prefs.theme && !applied.current) {
      applied.current = true;
      setTheme(prefs.theme);
    }
  }, [data, prefs.theme, setTheme]);
  return null;
}
