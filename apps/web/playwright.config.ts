import { defineConfig, devices } from "@playwright/test";

// Smoke + visual checks of the static showcase pages. The app is built from recorded
// fixtures and the API URL points at a dead port, proving these pages need no live API
// (CLAUDE.md rule 5, decision 0010). Screenshots land in test-results/shots/.
const PORT = 3200;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    // Software rendering: sandboxed/headless macOS sessions have no usable GPU.
    launchOptions: { args: ["--disable-gpu"] },
    // Full Chromium in new-headless mode; the stripped "headless shell" crashed in sandboxed sessions.
    channel: "chromium",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
    {
      name: "mobile",
      use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true },
    },
  ],
  webServer: {
    command: `pnpm build && pnpm start -p ${PORT} -H 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { SHOWCASE_FIXTURES: "1", NEXT_PUBLIC_API_URL: "http://127.0.0.1:9" },
  },
});
