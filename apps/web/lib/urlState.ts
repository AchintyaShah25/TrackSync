// Parse/serialize chart state in the URL so every view is shareable (new-chart skill §5).

export type SearchParams = Record<string, string | string[] | undefined>;

const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

/** "VER,nor,VER" → ["VER","NOR"], capped at `max`, only 3-letter codes. */
export function parseDriverCodes(value: string | string[] | undefined, max = 2): string[] {
  const raw = first(value) ?? "";
  const codes = raw
    .split(",")
    .map((c) => c.trim().toUpperCase())
    .filter((c) => /^[A-Z]{3}$/.test(c));
  return [...new Set(codes)].slice(0, max);
}

export function parseChoice<T extends string>(
  value: string | string[] | undefined,
  allowed: readonly T[],
  fallback: T,
): T {
  const v = first(value)?.toUpperCase();
  return (allowed as readonly string[]).includes(v ?? "") ? (v as T) : fallback;
}

/** Returns a new query string with `updates` applied (undefined/empty removes a key). */
export function withParams(
  current: URLSearchParams | string,
  updates: Record<string, string | string[] | undefined>,
): string {
  const next = new URLSearchParams(current);
  for (const [key, value] of Object.entries(updates)) {
    const v = Array.isArray(value) ? value.join(",") : value;
    if (v) next.set(key, v);
    else next.delete(key);
  }
  const s = next.toString();
  return s ? `?${s}` : "";
}
