import { defineConfig, devices } from "@playwright/test";

const SCHOOL_WEB = process.env.E2E_SCHOOL_WEB_URL ?? "http://localhost:5173";

export default defineConfig({
  testDir: "./tests",
  // The smoke flow is a single ordered scenario; keep it serial and readable.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: SCHOOL_WEB,
    actionTimeout: 20_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
      : undefined,
  },
});
