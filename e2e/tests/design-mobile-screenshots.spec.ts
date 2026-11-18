import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

/**
 * P0-21b mobile design-review screenshots, rendered through the Expo web
 * target at phone sizes. Start `pnpm --filter @erp/mobile web`, then:
 *
 *   RUN_MOBILE_SCREENSHOTS=1 pnpm --filter @erp/e2e exec playwright test \
 *     tests/design-mobile-screenshots.spec.ts
 *
 * Output: docs/review/p0/mobile-<screen>-<width>-<mode>-<locale>.png
 */

const RUN = process.env.RUN_MOBILE_SCREENSHOTS === "1";
const MOBILE_WEB = process.env.E2E_MOBILE_WEB_URL ?? "http://localhost:8081";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT_DIR = path.join(REPO_ROOT, "docs", "review", "p0");

const PHONES = [
  { name: "small", width: 390, height: 844 },
  { name: "large", width: 430, height: 932 },
] as const;

const SCREENS = ["list", "form", "dashboard"] as const;
const MODES = ["light", "dark"] as const;
const LOCALES = ["en", "am"] as const;

test.skip(!RUN, "set RUN_MOBILE_SCREENSHOTS=1 to capture the mobile design review");

async function setDesignState(page: Page, locale: string, mode: string): Promise<void> {
  // The toggle is labelled with the language it switches to.
  const localeLabel = (await page.getByTestId("design-locale").innerText()).trim();
  const targetLabel = locale === "en" ? "English" : "አማርኛ";
  if (localeLabel === targetLabel) {
    await page.getByTestId("design-locale").click();
  }
  const modeLabel = (await page.getByTestId("design-mode").innerText()).trim();
  const wantsLight = mode === "light";
  const showsSwitchToLight = modeLabel === "Light" || modeLabel === "ብርሃን";
  if (wantsLight === showsSwitchToLight) {
    await page.getByTestId("design-mode").click();
  }
  await page.waitForTimeout(150);
}

test("capture the mobile reference screens on small and large phones", async ({ browser }) => {
  test.setTimeout(8 * 60_000);
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto(`${MOBILE_WEB}/design`, { waitUntil: "domcontentloaded", timeout: 120_000 });
  await expect(page.getByTestId("design-tab-list")).toBeVisible({ timeout: 120_000 });

  for (const locale of LOCALES) {
    for (const mode of MODES) {
      await setDesignState(page, locale, mode);
      for (const phone of PHONES) {
        await page.setViewportSize({ width: phone.width, height: phone.height });
        for (const screen of SCREENS) {
          await page.getByTestId(`design-tab-${screen}`).click();
          await page.waitForTimeout(250);
          await page.screenshot({
            path: path.join(OUT_DIR, `mobile-${screen}-${phone.width}-${mode}-${locale}.png`),
          });
        }
      }
    }
  }

  await context.close();
});

test("capture the school picker", async ({ browser }) => {
  test.skip(!RUN, "set RUN_MOBILE_SCREENSHOTS=1 to capture the mobile design review");
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto(MOBILE_WEB, { waitUntil: "domcontentloaded", timeout: 120_000 });
  await expect(page.getByText("Choose your school", { exact: true })).toBeVisible({ timeout: 120_000 });
  for (const phone of PHONES) {
    await page.setViewportSize({ width: phone.width, height: phone.height });
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(OUT_DIR, `mobile-picker-${phone.width}-light-en.png`) });
  }
  await context.close();
});

test("capture the list states", async ({ browser }) => {
  test.skip(!RUN, "set RUN_MOBILE_SCREENSHOTS=1 to capture the mobile design review");
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto(`${MOBILE_WEB}/design`, { waitUntil: "domcontentloaded", timeout: 120_000 });
  await expect(page.getByTestId("design-tab-list")).toBeVisible({ timeout: 120_000 });
  for (const state of ["loading", "empty", "error"] as const) {
    await page.getByTestId(`design-state-${state}`).click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(OUT_DIR, `mobile-state-${state}-390-light-en.png`) });
  }
  await context.close();
});
