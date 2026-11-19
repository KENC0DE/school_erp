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
  const preview = page.getByTestId("preview-page");
  await expect(preview).toBeVisible();
  await expect(preview.getByText("New text Abebe Kebede Tadesse")).toBeVisible();
  await page.getByTestId("preview-close").click();

  await page.getByTestId("editor-back").click();
  await expect(page.getByTestId("documents-page")).toBeVisible();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
});
