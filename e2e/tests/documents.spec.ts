import { expect, test, type Page } from "@playwright/test";

const SCHOOL_WEB = process.env.E2E_SCHOOL_WEB_URL ?? "http://localhost:5173";
const SCHOOL_ADMIN = "superadmin@demo.school";
const PASSWORD = "DevPass#2026";

async function login(page: Page, email: string, password: string): Promise<void> {
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

test("design a certificate on the canvas, save the draft and preview it", async ({ page }) => {
  const name = `E2E certificate ${Date.now()}`;
  await page.goto(SCHOOL_WEB);
  await login(page, SCHOOL_ADMIN, PASSWORD);

  await page.getByRole("link", { name: "Document Studio" }).click();
  await expect(page.getByTestId("documents-page")).toBeVisible();

  await page.getByTestId("template-new").click();
  await page.getByTestId("template-name").fill(name);
  await page.getByTestId("template-starter").selectOption("certificate_completion");
  await page.getByTestId("template-create").click();

  await expect(page.getByTestId("template-editor")).toBeVisible();
  await page.getByTestId("add-text").click();
  await page.getByTestId("field-student.full_name").click();
  await expect(page.getByTestId("inspector-text")).toHaveValue(
    "New text {{student.full_name}}",
  );

  await page.getByTestId("editor-save").click();
  await expect(page.getByTestId("editor-notice")).toContainText("The draft was saved.");
  await expect(page.getByTestId("editor-save-state")).toContainText("All changes saved");

  await page.getByTestId("editor-preview").click();
  const sample = page.frameLocator('[data-testid="preview-frame"]');
  await expect(sample.getByText("New text Abebe Kebede Tadesse")).toBeVisible();

  await page.getByTestId("preview-mode-student").check();
  await page.getByTestId("preview-student-search").fill("STU-2026-0001");
  const student = page.getByTestId("preview-student");
  await expect(student.locator("option")).toHaveCount(2);
  await student.selectOption({ index: 1 });
  const real = page.frameLocator('[data-testid="preview-frame"]');
  await expect(real.getByText("New text Abebe Dawit Samuel")).toBeVisible();
  await page.getByTestId("preview-close").click();

  await page.getByTestId("editor-publish-open").click();
  await page.getByTestId("editor-publish").click();
  await expect(page.getByTestId("editor-notice")).toContainText("Version 1 published.");

  await page.getByTestId("editor-back").click();
  await expect(page.getByTestId("documents-page")).toBeVisible();
  await expect(page.getByText(name, { exact: true })).toBeVisible();

  // The published template can now be generated from the list. The e2e stack
  // has no Redis worker, so this checks authorisation and target selection
  // rather than waiting for a batch that cannot run here.
  const card = page.locator("article.doc-card").filter({ hasText: name });
  await card.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByTestId("generation-dialog")).toBeVisible();
  await page.getByTestId("generation-student-search").fill("STU-2026-0001");
  const picker = page.getByTestId("generation-student");
  await expect(picker.locator("option")).toHaveCount(2);
  await picker.selectOption({ index: 1 });
  await expect(page.getByTestId("generation-start")).toBeEnabled();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();

  await page.getByRole("link", { name: "Issued documents" }).click();
  await expect(page.getByTestId("issued-page")).toBeVisible();
});
