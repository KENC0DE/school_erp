import { execFile } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test, type Page } from "@playwright/test";

const run = promisify(execFile);

const CONTROLLER_WEB = process.env.E2E_CONTROLLER_WEB_URL ?? "http://localhost:5174";
const SCHOOL_WEB = process.env.E2E_SCHOOL_WEB_URL ?? "http://localhost:5173";
const OWNER_EMAIL = "owner@controller.local";
const OWNER_PASSWORD = "DevPass#2026";
const SCHOOL_ADMIN = "superadmin@demo.school";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

/**
 * Stands in for the Celery beat schedule while the smoke test runs: asks the
 * controller for the current license (module toggles) and ships queued audit
 * entries. Real deployments do this on a timer; the e2e stack has no Redis.
 */
async function syncSchoolWithController(): Promise<void> {
  await run("bash", [path.join(REPO_ROOT, "e2e", "sync.sh")], {
    cwd: REPO_ROOT,
    env: process.env,
  });
}

async function login(page: Page, email: string, password: string): Promise<void> {
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

test("controller drives module gating, support session and the audit vault", async ({ browser }) => {
  const noteText = `E2E support note ${Date.now()}`;
  const reason = "Smoke test: verify the support session";

  const controllerContext = await browser.newContext();
  const controller = await controllerContext.newPage();

  // 1. Controller login and the demo school detail page.
  await controller.goto(`${CONTROLLER_WEB}/login`);
  await login(controller, OWNER_EMAIL, OWNER_PASSWORD);
  await expect(controller.getByTestId("schools-page")).toBeVisible();

  await controller.getByTestId("school-row-DEMO").getByRole("link", { name: "Demo Academy" }).click();
  await expect(controller.getByTestId("school-detail-title")).toHaveText("Demo Academy");
  const sampleToggle = controller.getByTestId("module-toggle-sample");
  await expect(sampleToggle).toBeChecked();

  // 2. Disable the sample module; the school stops advertising it.
  await sampleToggle.click();
  await expect(controller.getByTestId("module-state-sample")).toHaveText("Off");
  await syncSchoolWithController();

  const schoolContext = await browser.newContext();
  const school = await schoolContext.newPage();
  await school.goto(SCHOOL_WEB);
  await login(school, SCHOOL_ADMIN, OWNER_PASSWORD);
  await expect(school.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  await school.reload();
  // After a reload the i18n bundle is fetched again; wait for the translated
  // heading rather than the raw key that is briefly rendered before it loads.
  await expect(school.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  await expect(school.getByRole("link", { name: "Sample module" })).toHaveCount(0);
  await expect(school.getByText("sample", { exact: true })).toHaveCount(0);

  // 3. Re-enable it; the menu comes back after the next heartbeat.
  await sampleToggle.click();
  await expect(controller.getByTestId("module-state-sample")).toHaveText("On");
  await syncSchoolWithController();
  await school.reload();
  await expect(school.getByRole("link", { name: "Sample module" }).first()).toBeVisible();

  // 4. Open an audited support session from the controller.
  await controller.getByTestId("open-support-session").click();
  const dialog = controller.getByTestId("support-session-dialog");
  await expect(dialog).toBeVisible();
  await controller.getByLabel("Reason for access").fill(reason);
  await controller.getByTestId("support-submit").click();
  const supportToken = (await controller.getByTestId("support-token").textContent())?.trim();
  expect(supportToken, "support session token").toBeTruthy();

  // The token is exchanged by the school web app in a fresh browser context.
  const supportContext = await browser.newContext();
  const support = await supportContext.newPage();
  await support.goto(
    `${SCHOOL_WEB}/controller-login?token=${encodeURIComponent(supportToken!)}&reason=${encodeURIComponent(reason)}`,
  );
  await expect(support.getByText("Controller support session").first()).toBeVisible();
  await expect(support.getByRole("link", { name: "Sample module" }).first()).toBeVisible();

  // 5. Perform a sample change as the controller actor.
  await support.getByRole("link", { name: "Sample module" }).first().click();
  await support.getByLabel("Write a note").fill(noteText);
  await support.getByRole("button", { name: "Add note" }).click();
  await expect(support.getByText(noteText).first()).toBeVisible();

  // 6. Ship the audit entry and check the vault labels it `via=controller`.
  await syncSchoolWithController();
  await controller.goto(`${CONTROLLER_WEB}/vault`);
  await expect(controller.getByTestId("vault-table")).toBeVisible();
  const row = controller
    .locator("[data-testid^='vault-row-']")
    .filter({ hasText: "sample.notes.create" })
    .first();
  await expect(row).toBeVisible();
  await expect(row.getByTestId("vault-via")).toHaveText("via=controller");
  const actor = row.locator("td").nth(4);
  await expect(actor).toContainText("controller");

  await supportContext.close();
  await schoolContext.close();
  await controllerContext.close();
});

test("removing a role permission hides that module from the menu", async ({ browser }) => {
  const adminContext = await browser.newContext();
  const admin = await adminContext.newPage();
  await admin.goto(SCHOOL_WEB);
  await login(admin, SCHOOL_ADMIN, OWNER_PASSWORD);

  await admin.getByRole("link", { name: "Roles", exact: true }).click();
  await expect(admin.getByTestId("roles-page")).toBeVisible();
  await admin.getByTestId("role-row-limited").click();
  const sampleView = admin.getByTestId("permission-sample.notes.view-all");
  await expect(sampleView).toBeChecked();
  await sampleView.uncheck();
  await admin.getByTestId("roles-save").click();
  await expect(admin.getByText("Role saved", { exact: true })).toBeVisible();

  const limitedContext = await browser.newContext();
  const limited = await limitedContext.newPage();
  await limited.goto(SCHOOL_WEB);
  await login(limited, "limited@demo.school", OWNER_PASSWORD);
  await expect(limited.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(limited.getByRole("link", { name: "Sample module" })).toHaveCount(0);

  await limitedContext.close();
  await adminContext.close();
});

test("super admin manages modules from settings", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(SCHOOL_WEB);
  await login(page, SCHOOL_ADMIN, OWNER_PASSWORD);

  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await expect(page.getByText("Choose which licensed modules this school can use.")).toBeVisible();
  await page.getByRole("link", { name: "Manage modules", exact: true }).click();

  await expect(page.getByTestId("modules-page")).toBeVisible();
  const sampleRow = page.getByTestId("module-row-sample");
  await expect(sampleRow.getByTestId("module-licensed-sample")).toHaveText("Yes");
  await expect(sampleRow.getByTestId("module-enabled-sample")).toHaveText("Yes");
  await expect(sampleRow.getByTestId("module-permitted-sample")).toHaveText("Yes");

  const toggle = sampleRow.getByTestId("module-toggle-sample");
  await expect(toggle).toBeChecked();
  await toggle.click();
  await expect(sampleRow.getByTestId("module-enabled-sample")).toHaveText("No");
  await expect(page.getByRole("link", { name: "Sample module" })).toHaveCount(0);

  await toggle.click();
  await expect(sampleRow.getByTestId("module-enabled-sample")).toHaveText("Yes");
  await expect(page.getByRole("link", { name: "Sample module" }).first()).toBeVisible();

  await context.close();
});
