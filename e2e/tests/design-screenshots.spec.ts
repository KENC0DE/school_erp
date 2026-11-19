import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

/**
 * P0-19b design-review screenshots. Not part of the smoke run: start the dev
 * stack, then
 *
 *   RUN_DESIGN_SCREENSHOTS=1 pnpm --filter @erp/e2e exec playwright test \
 *     tests/design-screenshots.spec.ts
 *
 * Output: docs/review/p0/<screen>-<width>-<mode>-<locale>.png
 */

const RUN = process.env.RUN_DESIGN_SCREENSHOTS === "1";
const SCHOOL_WEB = process.env.E2E_SCHOOL_WEB_URL ?? "http://localhost:5173";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT_DIR = path.join(REPO_ROOT, "docs", "review", "p0");
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";

const WIDTHS = [1440, 768, 390] as const;
const SCREENS = ["list", "form", "dashboard"] as const;
const MODES = ["light", "dark"] as const;
const LOCALES = ["en", "am"] as const;

test.skip(!RUN, "set RUN_DESIGN_SCREENSHOTS=1 to capture the design review");

async function login(page: Page): Promise<void> {
  await page.goto(SCHOOL_WEB);
  await page.getByLabel("Email", { exact: true }).fill("superadmin@demo.school");
  await page.getByLabel("Password", { exact: true }).fill("DevPass#2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
}

/**
 * The active theme mode is a server-side preference, so switching it through
 * localStorage alone would be overwritten on load. Persist it through the API.
 */
async function setThemeMode(page: Page, mode: string): Promise<void> {
  await page.evaluate(
    async ([apiUrl, nextMode]) => {
      const token = localStorage.getItem("erp.access_token");
      await fetch(`${apiUrl}/api/v1/themes/preference`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ theme_key: null, mode: nextMode }),
      });
    },
    [API_URL, mode],
  );
}

async function prepare(page: Page, mode: string, locale: string, width: number): Promise<void> {
  await page.setViewportSize({ width, height: width === 390 ? 844 : width === 768 ? 1024 : 900 });
  await page.evaluate((nextLocale) => {
    localStorage.setItem("erp.locale", nextLocale);
  }, locale);
  await page.goto(`${SCHOOL_WEB}/design`);
  await expect(page.getByRole("tab").first()).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(
    (dark) => document.documentElement.classList.contains("dark") === dark,
    mode === "dark",
  );
  // Let the theme tokens and translated bundle settle before the capture.
  await page.waitForTimeout(400);
}

test("capture the three reference screens", async ({ browser }) => {
  test.setTimeout(10 * 60_000);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await login(page);

  let appliedMode: string | null = null;
  for (const locale of LOCALES) {
    for (const mode of MODES) {
      if (mode !== appliedMode) {
        await setThemeMode(page, mode);
        appliedMode = mode;
      }
      for (const width of WIDTHS) {
        await prepare(page, mode, locale, width);
        const tabs = page.getByRole("tab");
        for (let index = 0; index < SCREENS.length; index += 1) {
          await tabs.nth(index).click();
          await page.waitForTimeout(250);
          await page.screenshot({
            path: path.join(OUT_DIR, `${SCREENS[index]}-${width}-${mode}-${locale}.png`),
            fullPage: true,
          });
        }
        // The shell itself is part of the foundation: capture it once per size.
        await page.goto(SCHOOL_WEB);
        await expect(page.getByRole("heading", { level: 1 })).toHaveText(
          locale === "am" ? "ዳሽቦርድ" : "Dashboard",
        );
        await page.waitForTimeout(350);
        await page.screenshot({
          path: path.join(OUT_DIR, `shell-${width}-${mode}-${locale}.png`),
          fullPage: true,
        });
        if (width === 390) {
          await page.getByRole("button", { name: locale === "am" ? "ምናሌ" : "Menu" }).click();
          await expect(page.locator(".ui-sidebar--open")).toBeVisible();
          await page.waitForTimeout(200);
          await page.screenshot({
            path: path.join(OUT_DIR, `nav-390-${mode}-${locale}.png`),
          });
        }
      }
    }
  }

  await context.close();
});
