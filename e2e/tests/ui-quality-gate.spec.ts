import path from "node:path";
import { fileURLToPath } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  checkScreenStates,
  lowContrastCss,
  recolouredCss,
  screenStateGaps,
} from "../lib/ui-gate";

/**
 * P1-27 UI quality gate.
 *
 * Runs on the seeded stack (`./e2e/run.sh`). The axe, state and theme checks
 * always run; the screenshot matrix is opt-in because it writes review files:
 *
 *   RUN_UI_GATE_SCREENSHOTS=1 pnpm --filter @erp/e2e exec playwright test \
 *     tests/ui-quality-gate.spec.ts
 */

const CAPTURE = process.env.RUN_UI_GATE_SCREENSHOTS === "1";
const SCHOOL_WEB = process.env.E2E_SCHOOL_WEB_URL ?? "http://localhost:5173";
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT_DIR = path.join(REPO_ROOT, "docs", "review", "p1");

const ADMIN = { email: "superadmin@demo.school", password: "DevPass#2026" };
const WIDTHS = [1440, 768, 390] as const;
const MODES = ["light", "dark"] as const;
const LOCALES = ["en", "am"] as const;

/** The screens reviewed at every size, mode and language. */
const KEY_SCREENS = [
  { name: "dashboard", path: "/" },
  { name: "users", path: "/users" },
  { name: "academics", path: "/academics" },
  { name: "design", path: "/design" },
] as const;

/** Every screen that the axe sweep covers. */
const AXE_SCREENS = [
  "/",
  "/activity",
  "/users",
  "/roles",
  "/academics",
  "/students",
  "/settings/modules",
  "/settings/languages",
  "/settings/themes",
  "/notifications",
  "/jobs",
  "/sample",
  "/design",
  "/documents",
  "/documents/issued",
] as const;

async function login(page: Page): Promise<void> {
  await page.goto(SCHOOL_WEB);
  await page.getByLabel("Email", { exact: true }).fill(ADMIN.email);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

async function token(page: Page): Promise<string> {
  return page.evaluate(() => localStorage.getItem("erp.access_token") ?? "");
}

/**
 * Theme mode is a server-side preference. Persist it through the API so the
 * next navigation renders with the right tokens instead of flashing.
 */
async function setThemeMode(page: Page, mode: "light" | "dark"): Promise<void> {
  const bearer = await token(page);
  const response = await page.request.put(`${API_URL}/api/v1/themes/preference`, {
    headers: { Authorization: `Bearer ${bearer}` },
    data: { theme_key: null, mode },
  });
  expect(response.ok()).toBeTruthy();
}

async function prepare(
  page: Page,
  mode: "light" | "dark",
  locale: string,
  width: number,
  target: string,
): Promise<void> {
  await page.setViewportSize({
    width,
    height: width === 390 ? 844 : width === 768 ? 1024 : 900,
  });
  await page.evaluate((nextLocale) => {
    localStorage.setItem("erp.locale", nextLocale);
  }, locale);
  await page.goto(`${SCHOOL_WEB}${target}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(
    (dark) => document.documentElement.classList.contains("dark") === dark,
    mode === "dark",
  );
  await page.waitForTimeout(350);
}

async function overflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

/** Structural metrics that a theme must not change. */
async function layoutMetrics(page: Page): Promise<Record<string, unknown>> {
  return page.evaluate(() => {
    const heading = document.querySelector("h1");
    const card = document.querySelector(".ui-card");
    const sidebar = document.querySelector(".ui-sidebar");
    const cardStyle = card ? getComputedStyle(card) : null;
    const headingStyle = heading ? getComputedStyle(heading) : null;
    return {
      headingFontSize: headingStyle?.fontSize ?? null,
      headingLineHeight: headingStyle?.lineHeight ?? null,
      cardPadding: cardStyle
        ? [cardStyle.paddingTop, cardStyle.paddingInlineStart, cardStyle.paddingBottom].join(" ")
        : null,
      sidebarWidth: sidebar ? Math.round(sidebar.getBoundingClientRect().width) : null,
      bodyFontSize: getComputedStyle(document.body).fontSize,
    };
  });
}

test("the state check passes for every data screen", () => {
  expect(screenStateGaps(REPO_ROOT)).toEqual([]);
  expect(() => checkScreenStates(REPO_ROOT)).not.toThrow();
});

test("the state check rejects a screen without an empty state", () => {
  const fixture = "e2e/fixtures/ui-gate/missing-empty-state.tsx";
  const gaps = screenStateGaps(REPO_ROOT, [fixture]);
  expect(gaps).toEqual([{ file: fixture, missing: ["EmptyState"] }]);
  expect(() => checkScreenStates(REPO_ROOT, [fixture])).toThrow(/missing EmptyState/);
});

test("the theme check rejects a low-contrast community theme", async ({ page }) => {
  await login(page);
  const bearer = await token(page);
  const active = await page.request.get(`${API_URL}/api/v1/themes/active`);
  const tokens = (await active.json()).tokens as Record<string, Record<string, string>>;

  const response = await page.request.post(`${API_URL}/api/v1/themes/preview`, {
    headers: { Authorization: `Bearer ${bearer}` },
    data: {
      format: "css",
      content: lowContrastCss(tokens),
      name: "Low contrast fixture",
      key: "low-contrast-fixture",
    },
  });
  expect(response.ok()).toBeTruthy();
  const preview = await response.json();
  expect(preview.valid).toBe(false);
  expect(preview.issues.map((issue: { code: string }) => issue.code)).toContain("contrast");
});

test("a community theme cannot move layout or inject CSS", async ({ page }) => {
  await login(page);
  await setThemeMode(page, "light");
  await prepare(page, "light", "en", 1440, "/");

  const bearer = await token(page);
  const active = await page.request.get(`${API_URL}/api/v1/themes/active`);
  const tokens = (await active.json()).tokens as Record<string, Record<string, string>>;

  const before = await layoutMetrics(page);
  const response = await page.request.post(`${API_URL}/api/v1/themes/preview`, {
    headers: { Authorization: `Bearer ${bearer}` },
    data: {
      format: "css",
      content: recolouredCss(tokens),
      name: "Community recolour",
      key: "community-recolour",
    },
  });
  expect(response.ok()).toBeTruthy();
  const preview = await response.json();
  expect(preview.valid).toBe(true);

  const injectedTokens = {
    light: { ...tokens.light, "font-sans": "Inter; } body { display: none } /*" },
    dark: { ...tokens.dark },
  };
  const injected = await page.request.post(`${API_URL}/api/v1/themes/preview`, {
    headers: { Authorization: `Bearer ${bearer}` },
    data: {
      format: "json",
      content: JSON.stringify({ name: "Injection fixture", tokens: injectedTokens }),
      name: "Injection fixture",
      key: "injection-fixture",
    },
  });
  expect(injected.ok()).toBeTruthy();
  const rejected = await injected.json();
  expect(rejected.valid).toBe(false);
  expect(rejected.issues.map((issue: { code: string }) => issue.code)).toContain("unsafe_value");

  // Apply the accepted theme exactly as the ThemeProvider would: only CSS
  // variables change, so spacing, type size and the shell do not move.
  await page.evaluate((light) => {
    for (const [key, value] of Object.entries(light)) {
      document.documentElement.style.setProperty(`--${key}`, value);
    }
  }, preview.tokens.light);
  await page.waitForTimeout(150);

  expect(await layoutMetrics(page)).toEqual(before);
  expect(await overflow(page)).toBeLessThanOrEqual(0);
});

test("axe finds no serious or critical violations", async ({ browser }) => {
  test.setTimeout(5 * 60_000);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await login(page);
  await setThemeMode(page, "light");

  const failures: string[] = [];
  for (const target of AXE_SCREENS) {
    await prepare(page, "light", "en", 1440, target);
    if (target === "/design") {
      await page.getByRole("tab").nth(1).click();
      await page.waitForTimeout(400);
    }
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    for (const violation of results.violations) {
      if (violation.impact === "serious" || violation.impact === "critical") {
        failures.push(`${target} ${violation.id} (${violation.nodes.length})`);
      }
    }
  }

  // Dark mode and phone width are both first-class, so sample them too.
  await setThemeMode(page, "dark");
  for (const target of ["/", "/users", "/settings/themes"]) {
    await prepare(page, "dark", "en", 390, target);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    for (const violation of results.violations) {
      if (violation.impact === "serious" || violation.impact === "critical") {
        failures.push(`${target} dark/390 ${violation.id} (${violation.nodes.length})`);
      }
    }
  }

  expect(failures).toEqual([]);
  await context.close();
});

test("capture the key screens at every width, mode and language", async ({ browser }) => {
  test.skip(!CAPTURE, "set RUN_UI_GATE_SCREENSHOTS=1 to write the review screenshots");
  test.setTimeout(20 * 60_000);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await login(page);

  let appliedMode: "light" | "dark" | null = null;
  for (const locale of LOCALES) {
    for (const mode of MODES) {
      if (mode !== appliedMode) {
        await setThemeMode(page, mode);
        appliedMode = mode;
      }
      for (const width of WIDTHS) {
        for (const screen of KEY_SCREENS) {
          await prepare(page, mode, locale, width, screen.path);
          expect(await overflow(page), `${screen.name} ${width} ${mode} ${locale}`).toBeLessThanOrEqual(
            0,
          );
          await page.screenshot({
            path: path.join(OUT_DIR, `${screen.name}-${width}-${mode}-${locale}.png`),
            fullPage: true,
          });
        }
      }
    }
  }

  await context.close();
});

test("long Amharic text wraps without clipping or horizontal scroll", async ({ browser }) => {
  test.skip(!CAPTURE, "set RUN_UI_GATE_SCREENSHOTS=1 to write the review screenshots");
  test.setTimeout(5 * 60_000);

  const longTitle = "ዳሽቦርድ — የትምህርት ቤቱ አጠቃላይ ሁኔታና የቅርብ ጊዜ እንቅስቃሴዎች በአንድ ገጽ ላይ";
  const longIntro =
    "ይህ ገጽ የትምህርት ቤቱን የተማሪዎች ቁጥር፣ የሰራተኞች ሁኔታ፣ የክፍያ መረጃና የቅርብ ጊዜ ማሳወቂያዎች በአንድ ቦታ ያሳያል።";
  const context: BrowserContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.route("**/api/v1/i18n/am/**", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.messages["dashboard.title"] = longTitle;
    body.messages["dashboard.subtitle"] = longIntro;
    await route.fulfill({ response, json: body });
  });
  const page = await context.newPage();
  await login(page);
  await setThemeMode(page, "light");

  for (const width of [1440, 390] as const) {
    await prepare(page, "light", "am", width, "/");
    expect(await page.getByRole("heading", { level: 1 }).innerText()).toContain("ዳሽቦርድ");
    expect(await overflow(page), `long Amharic at ${width}`).toBeLessThanOrEqual(0);
    await page.screenshot({
      path: path.join(OUT_DIR, `long-amharic-dashboard-${width}.png`),
      fullPage: true,
    });
  }

  await context.close();
});
