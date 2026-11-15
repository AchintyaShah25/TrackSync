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

// The API's /chat (a dead port in e2e), not the site's /chat page (decision 0033).
const API_CHAT = (url: URL) => url.port === "9" && url.pathname === "/chat";

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
      await expect(page.locator("section[aria-labelledby=examples] li")).toHaveCount(5);
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

    // Why: the outcome fan chart is the project's signature visual (SPEC M2). The showcase
    // forecast is simulated at build time, so it must render fully with the API asleep.
    test(`forecast showcase draws the fan chart and odds (${scheme})`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto("/races/2024/16/forecast");
      const fan = page.locator("figure[aria-label^='Strategy forecast for Oscar Piastri']");
      await expect(fan).toBeVisible();
      expect(await fan.locator(".recharts-area").count()).toBeGreaterThanOrEqual(4); // 2 strategies × 2 bands
      await expect(fan.locator(".recharts-line")).toHaveCount(2);
      await expect(page.locator("figure[aria-label^='Finishing position odds']")).toBeVisible();
      await expect(page.getByText(/than the real strategy \(median\)/).first()).toBeVisible();
      await expect(page.getByRole("tab", { name: "Forecast" }).or(page.getByRole("link", { name: "Forecast" }))).toHaveAttribute(
        "aria-current",
        "page",
      );
      await noHorizontalOverflow(page);
      await shot(page, "forecast", scheme);
      expect(errors).toEqual([]);
    });

    // Why: illegal or short strategies are blocked in the browser before any API call
    // (user decision: block, don't just warn).
    test(`forecast builder validates strategies (${scheme})`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto("/races/2024/16/forecast");
      const simulate = page.getByRole("button", { name: "Simulate" });
      await expect(simulate).toBeDisabled(); // nothing changed yet
      await page.getByRole("button", { name: "Strategy A, stint 2 laps: one fewer" }).click();
      await expect(page.getByText("1 more lap needed (race is 53).")).toBeVisible();
      await expect(simulate).toBeDisabled();
      const radios = page.getByRole("radiogroup", { name: "Strategy A, stint 2 compound" });
      await page.getByRole("button", { name: "Strategy A, stint 2 laps: one more" }).click();
      await radios.getByRole("radio", { name: "M" }).click();
      await expect(page.getByText("A dry race must use at least two different compounds.")).toBeVisible();
      await radios.getByRole("radio", { name: "H" }).click();
      await expect(page.getByText(/must use at least two/)).toHaveCount(0);
      expect(errors).toEqual([]);
    });

    // Why: the chat agent is the third hero feature. The API is a dead port in e2e, so /chat
    // is mocked at the browser (decision 0033); this checks the UI contract: cited sources,
    // licence lines, an inline chart and the privacy notice, on desktop and mobile.
    test(`chat renders a cited answer with a chart (${scheme})`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.route(API_CHAT, (route) =>
        route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            answer: "Cars must queue behind the **safety car** within ten car lengths [1].\n\n- Norris finished ahead 16 times [2]",
            sources: [
              { n: 1, title: "2026 F1 Sporting Regulations", section: "Article B5.13 Safety Car (SC)", url: "https://www.fia.com/x.pdf", license: "© FIA. Excerpt quoted for reference.", source: "fia", excerpt: "…" },
              { n: 2, title: "2024 Formula One World Championship", section: "Season summary", url: "https://en.wikipedia.org/wiki/2024_Formula_One_World_Championship", license: "CC BY-SA 4.0 (Wikipedia contributors)", source: "wikipedia", excerpt: "…" },
            ],
            charts: [{ type: "line", title: "Finishing positions 2024", x_label: "Round", y_label: "Position",
              series: [{ name: "NOR", points: [[1, 6], [2, 8], [3, 2]] }, { name: "PIA", points: [[1, 8], [2, 4], [3, 4]] }] }],
            tools_used: ["search_knowledge", "query_stats", "make_chart"],
            provider: "fake", model: "fake",
          }),
        }),
      );
      await page.goto("/chat");
      await expect(page.getByText(/free AI providers/)).toBeVisible();
      await page.getByRole("button", { name: "What happens when the safety car comes out?" }).click();
      const log = page.getByRole("log");
      await expect(log.getByText("safety car", { exact: true })).toBeVisible();
      await expect(log.getByRole("link", { name: "Source 1" })).toHaveAttribute("href", /-src-1$/);
      await expect(log.getByText("CC BY-SA 4.0 (Wikipedia contributors)")).toBeVisible();
      await expect(log.locator("figure .recharts-line")).toHaveCount(2);
      await expect(log.getByText(/looked up stats/)).toBeVisible();
      await noHorizontalOverflow(page);
      await shot(page, "chat", scheme);
      expect(errors).toEqual([]);
    });

    // Why: rate limits are part of demo mode; the user must see why and when to retry.
    test(`chat explains a rate limit (${scheme})`, async ({ page }) => {
      await page.route(API_CHAT, (route) =>
        route.fulfill({ status: 429, contentType: "application/json", headers: { "Retry-After": "120" },
          body: JSON.stringify({ detail: "you have used today's 30 questions; sign in for more; it resets at midnight UTC" }) }),
      );
      await page.goto("/chat");
      await page.getByLabel("Your question").fill("Who won Monza 2024?");
      await page.getByRole("button", { name: "Send" }).click();
      await expect(page.getByRole("alert").filter({ hasText: "sign in for more" })).toBeVisible();
      await expect(page.getByLabel("Your question")).toHaveValue("Who won Monza 2024?"); // kept to retry
    });

    // Why: demo mode: guests use every feature; saving is the only thing that asks to sign in.
    test(`guests are invited to sign in to save (${scheme})`, async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto("/races/2024/16/forecast");
      const save = page.getByRole("link", { name: "Sign in to save" });
      await expect(save).toBeVisible();
      await expect(save).toHaveAttribute("href", /^\/login\?next=%2Fraces%2F2024%2F16%2Fforecast/);
      await save.click();
      await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
      await expect(page.getByLabel("Email")).toBeVisible();
      await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible(); // header
      await noHorizontalOverflow(page);
      await shot(page, "login", scheme);
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
