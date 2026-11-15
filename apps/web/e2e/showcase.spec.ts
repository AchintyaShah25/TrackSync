import { existsSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

/**
 * Collect JS errors and failed requests during a test. Next prefetches linked race pages in
 * the background (`_rsc` requests); in fixture mode non-showcase races have no snapshot and
 * 404, which is expected here and harmless in production, so those are ignored. The
 * browser's generic "Failed to load resource" console line is replaced by the response check.
 */
function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("response", (r) => {
    const url = new URL(r.url());
    if (r.status() >= 400 && !url.searchParams.has("_rsc")) errors.push(`${r.status()} ${url.pathname}`);
  });
  return errors;
}

async function noHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page must not scroll sideways").toBeLessThanOrEqual(1);
}

async function shot(page: Page, name: string, scheme: string) {
  const project = test.info().project.name;
  await page.screenshot({ path: `test-results/shots/${project}-${scheme}-${name}.png`, fullPage: true });
}

// Playwright runs from apps/web (package is ESM, so no __dirname).
const fixture = (name: string) => existsSync(path.join(process.cwd(), "fixtures", "api", name));

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    // Why: the landing page is the first thing a reviewer sees and must work with the API asleep.
    test(`landing page renders examples and countdown (${scheme})`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Start with an example" })).toBeVisible();
      await expect(page.locator("section[aria-labelledby=examples] li")).toHaveCount(4);
      await expect(page.getByText(/not affiliated with/i)).toBeVisible();
      await noHorizontalOverflow(page);
      await shot(page, "landing", scheme);
      expect(errors).toEqual([]);
    });

    // Why: the telemetry comparison is the headline chart; it must draw all four panels
    // from build-time data without any API call.
    test(`telemetry showcase draws four synced panels (${scheme})`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto("/races/2024/16/telemetry?session=Q&drivers=VER,NOR");
      const figure = page.locator("figure[aria-label^='Telemetry comparison']");
      await expect(figure).toBeVisible();
      await expect(figure.locator("svg.recharts-surface")).toHaveCount(4);
      await expect(figure.locator(".recharts-line")).toHaveCount(8); // 4 panels × 2 drivers
      await expect(page.getByText("Gap")).toBeVisible();
      await noHorizontalOverflow(page);
      await shot(page, "telemetry", scheme);
      expect(errors).toEqual([]);
    });

    // Why: the strategy timeline must show one bar row per classified driver.
    test(`strategy showcase draws stint bars (${scheme})`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto("/races/2024/21/strategy");
      const figure = page.locator("figure[aria-label^='Tire strategy']");
      await expect(figure).toBeVisible();
      expect(await figure.locator(".recharts-bar-rectangle").count()).toBeGreaterThan(20);
      await expect(page.getByRole("list", { name: "Compounds" })).toContainText("Inter");
      await noHorizontalOverflow(page);
      await shot(page, "strategy", scheme);
      expect(errors).toEqual([]);
    });

    // Why: results and standings tables are the plain-data backbone of the site.
    test(`race results and season standings render (${scheme})`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto("/races/2024/16");
      await expect(page.getByRole("heading", { name: "Race" })).toBeVisible();
      expect(await page.locator("table").first().locator("tbody tr").count()).toBeGreaterThanOrEqual(19);
      await noHorizontalOverflow(page);
      await shot(page, "results", scheme);
      await page.goto("/seasons/2024");
      await expect(page.getByRole("heading", { name: "Drivers" })).toBeVisible();
      await noHorizontalOverflow(page);
      await shot(page, "season", scheme);
      expect(errors).toEqual([]);
    });

    // Why: the speed-colored track map is the third hero chart (hand-rolled SVG).
    test(`track map showcase draws colored segments (${scheme})`, async ({ page }) => {
      test.skip(!fixture("events_202508.json"), "Monaco 2025 not ingested/recorded yet");
      const errors = watchErrors(page);
      await page.goto("/races/2025/8/track");
      const map = page.getByRole("img", { name: /Track map of/ });
      await expect(map).toBeVisible();
      expect(await map.locator("line").count()).toBeGreaterThan(250);
      await noHorizontalOverflow(page);
      await shot(page, "track", scheme);
      expect(errors).toEqual([]);
    });
  });
}
