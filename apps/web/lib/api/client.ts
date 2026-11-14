// Tiny typed fetch wrapper used by both server components (build time) and the browser.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

/** Server-side fetches may use a private URL (e.g. http://api:8000 inside compose). */
function baseUrl(): string {
  if (typeof window === "undefined" && process.env.INTERNAL_API_URL) {
    return process.env.INTERNAL_API_URL.replace(/\/$/, "");
  }
  return API_URL;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface FetchOptions {
  signal?: AbortSignal;
  /** Build-time fetches retry to give a sleeping free-tier API time to wake. */
  retries?: number;
  timeoutMs?: number;
  /** Extra fetch init, e.g. Next's `{ next: { revalidate: 86400 } }` on the server. */
  init?: RequestInit & { next?: { revalidate?: number | false; tags?: string[] } };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function apiGet<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { retries = 0, timeoutMs = 20_000 } = opts;
  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const onAbort = () => controller.abort();
    opts.signal?.addEventListener("abort", onAbort);
    try {
      const res = await fetch(`${baseUrl()}${path}`, {
        ...opts.init,
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      if (res.ok) return (await res.json()) as T;
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* non-JSON error body */
      }
      // 4xx are final; 5xx (or a cold-starting proxy) are worth retrying.
      if (res.status < 500) throw new ApiError(res.status, String(detail));
      lastError = new ApiError(res.status, String(detail));
    } catch (err) {
      if (err instanceof ApiError && err.status < 500) throw err;
      if (opts.signal?.aborted) throw err;
      lastError = err;
    } finally {
      clearTimeout(timer);
      opts.signal?.removeEventListener("abort", onAbort);
    }
    if (attempt < retries) await sleep(Math.min(2000 * 2 ** attempt, 15_000));
  }
  throw lastError instanceof Error ? lastError : new Error("request failed");
}

export const paths = {
  seasons: () => "/seasons",
  events: (year: number) => `/seasons/${year}/events`,
  event: (id: number) => `/events/${id}`,
  results: (id: number, session = "R") => `/events/${id}/results?session=${session}`,
  stints: (id: number, session = "R") => `/events/${id}/stints?session=${session}`,
  traces: (id: number, drivers: string[], session = "Q") =>
    `/events/${id}/traces?session=${session}&drivers=${drivers.map(encodeURIComponent).join(",")}`,
  standings: (year: number) => `/standings/${year}`,
  circuit: (id: string) => `/circuits/${encodeURIComponent(id)}`,
};
