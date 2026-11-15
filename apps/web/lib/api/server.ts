// Server-component data access. Pages using this are statically generated and revalidated
// daily (ISR), so they keep serving instantly while the free API sleeps (decision 0010).
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { apiGet, apiPost, ApiError } from "./client";

export const REVALIDATE_SECONDS = 86400;

const FIXTURE_DIR = path.join(process.cwd(), "fixtures", "api");

/** Stable file name for an API path: "/events/202416/traces?session=Q&drivers=VER,NOR" */
export function fixtureName(apiPath: string): string {
  return apiPath.replace(/^\//, "").replace(/[^a-zA-Z0-9]+/g, "_") + ".json";
}

/**
 * GET for server components. With SHOWCASE_FIXTURES=1 (CI builds) reads snapshots from
 * fixtures/api/ instead of the network; a missing snapshot behaves like a 404.
 */
export async function serverGet<T>(apiPath: string): Promise<T> {
  if (process.env.SHOWCASE_FIXTURES === "1") {
    try {
      return JSON.parse(await readFile(path.join(FIXTURE_DIR, fixtureName(apiPath)), "utf8")) as T;
    } catch {
      throw new ApiError(404, `no fixture for ${apiPath}`);
    }
  }
  const data = await apiGet<T>(apiPath, {
    retries: 4, // ~1 min of retries lets a sleeping Render instance wake during builds
    timeoutMs: 30_000,
    init: { next: { revalidate: REVALIDATE_SECONDS } },
  });
  if (process.env.SHOWCASE_RECORD === "1") await record(apiPath, data);
  return data;
}

/** SHOWCASE_RECORD=1 next build: snapshot every API response the build used (for CI). */
async function record(apiPath: string, data: unknown) {
  await mkdir(FIXTURE_DIR, { recursive: true });
  await writeFile(path.join(FIXTURE_DIR, fixtureName(apiPath)), JSON.stringify(data));
}

/** Like serverGet, but resolves to null on 404 (for notFound() handling). */
export async function serverGetOrNull<T>(apiPath: string): Promise<T | null> {
  try {
    return await serverGet<T>(apiPath);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/** Fixture name for a POST: the path plus a short hash of the JSON body. */
export function postFixtureName(apiPath: string, body: unknown): string {
  const hash = createHash("sha256").update(JSON.stringify(body)).digest("hex").slice(0, 12);
  return fixtureName(apiPath).replace(/\.json$/, `_${hash}.json`);
}

/**
 * POST for server components (static forecast examples). Same fixture rules as serverGet,
 * keyed by path + body hash. Not cached by Next's fetch cache; the page's ISR covers it.
 */
export async function serverPostOrNull<T>(apiPath: string, body: unknown): Promise<T | null> {
  const file = path.join(FIXTURE_DIR, postFixtureName(apiPath, body));
  if (process.env.SHOWCASE_FIXTURES === "1") {
    try {
      return JSON.parse(await readFile(file, "utf8")) as T;
    } catch {
      return null;
    }
  }
  try {
    const data = await apiPost<T>(apiPath, body, { retries: 4, timeoutMs: 30_000 });
    if (process.env.SHOWCASE_RECORD === "1") {
      await mkdir(FIXTURE_DIR, { recursive: true });
      await writeFile(file, JSON.stringify(data));
    }
    return data;
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) return null;
    throw err;
  }
}
