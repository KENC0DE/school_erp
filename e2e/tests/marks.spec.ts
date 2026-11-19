import { expect, test, type Page } from "@playwright/test";

const SCHOOL_WEB = process.env.E2E_SCHOOL_WEB_URL ?? "http://localhost:5173";
const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const SCHOOL_ADMIN = "superadmin@demo.school";
const PASSWORD = "DevPass#2026";

interface Year {
  id: string;
  current_term_id: string | null;
  terms: { id: string }[];
}

interface Section {
  id: string;
  year_id: string;
  level_name: string;
  code: string;
}

interface Subject {
  id: string;
  code: string;
  name: string;
}

interface Structure {
  id: string;
  scope_type: string;
  components: { key: string; max_points: string }[];
}

interface AssessmentRow {
  id: string;
  title: string;
  assessment_date: string;
}

interface AssessmentList {
  items: AssessmentRow[];
}

interface ScoreSheet {
  items: { raw_score: string | null }[];
}

async function login(page: Page): Promise<void> {
  await page.goto(SCHOOL_WEB);
  await page.getByLabel("Email", { exact: true }).fill(SCHOOL_ADMIN);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

async function apiLogin(): Promise<string> {
  const response = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: SCHOOL_ADMIN, password: PASSWORD }),
  });
  if (response.status !== 200) {
    throw new Error(
      `login failed: ${response.status} ${await response.text()}`,
    );
  }
  const payload = (await response.json()) as {
    tokens: { access_token: string };
  };
  return payload.tokens.access_token;
}

async function api<T>(
  token: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (response.status >= 400) {
    throw new Error(
      `${init.method ?? "GET"} ${path}: ${response.status} ${await response.text()}`,
    );
  }
  return (await response.json()) as T;
}

async function prepareAssessments(): Promise<string[]> {
  const token = await apiLogin();
  const years = await api<{ items: Year[]; current_year_id: string | null }>(
    token,
    "/api/v1/academics/academic-years",
  );
  const year =
    years.items.find((item) => item.id === years.current_year_id) ??
    years.items[0];
  expect(year, "current academic year").toBeTruthy();
  const termId = year.current_term_id ?? year.terms[0]?.id;
  expect(termId, "current term").toBeTruthy();

  const sections = await api<{ items: Section[] }>(
    token,
    `/api/v1/academics/sections?year_id=${year.id}`,
  );
  const section = sections.items.find(
    (item) =>
      item.year_id === year.id &&
      item.level_name === "Grade 5" &&
      item.code === "A",
  );
  expect(section, "Grade 5 Section A").toBeTruthy();

  const subjects = await api<{ items: Subject[] }>(
    token,
    "/api/v1/academics/subjects",
  );
  const subject = subjects.items.find((item) => item.code === "english");
  expect(subject, "English subject").toBeTruthy();

  const structures = await api<{ items: Structure[] }>(
    token,
    `/api/v1/assessment/structures?year_id=${year.id}&limit=200`,
  );
  const structure =
    structures.items.find((item) => item.scope_type === "school") ??
    structures.items[0];
  expect(structure, "a mark structure").toBeTruthy();
  const component =
    structure.components.find((item) => item.key === "quizzes") ??
    structure.components[0];
  expect(component, "a structure component").toBeTruthy();
  const outOf = Number(component.max_points) > 0 ? component.max_points : "10";

  const existing = await api<AssessmentList>(
    token,
    `/api/v1/assessment/assessments?year_id=${year.id}&section_id=${section!.id}&subject_id=${subject!.id}&limit=200`,
  );
  const ours = existing.items.filter((item) =>
    item.title.startsWith("E2E Quiz "),
  );
  for (let index = ours.length; index < 10; index += 1) {
    await api<AssessmentRow>(token, "/api/v1/assessment/assessments", {
      method: "POST",
      body: JSON.stringify({
        year_id: year.id,
        term_id: termId,
        section_id: section!.id,
        subject_id: subject!.id,
        structure_id: structure!.id,
        component_key: component!.key,
        title: `E2E Quiz ${index + 1}`,
        assessment_date: `2026-10-${String(index + 1).padStart(2, "0")}`,
        out_of: outOf,
      }),
    });
  }

  const all = await api<AssessmentList>(
    token,
    `/api/v1/assessment/assessments?year_id=${year.id}&section_id=${section!.id}&subject_id=${subject!.id}&limit=200`,
  );
  return all.items
    .filter((item) => item.title.startsWith("E2E Quiz "))
    .sort((left, right) =>
      left.assessment_date.localeCompare(right.assessment_date),
    )
    .slice(0, 10)
    .map((item) => item.id);
}

test("enters thirty marks with the keyboard and a pasted column", async ({
  page,
}) => {
  const assessmentIds = await prepareAssessments();

  await login(page);
  await page.goto(`${SCHOOL_WEB}/assessment`);
  await page.getByTestId("assessment-tab-marks").click();

  await expect(page.getByTestId("mark-entry-panel")).toBeVisible();
  await expect(page.getByTestId("mark-section")).toContainText("Grade 5");
  await page.getByTestId("mark-section").selectOption({ label: "Grade 5 A" });
  await expect(page.getByTestId("mark-subject")).toContainText("English");
  await page.getByTestId("mark-subject").selectOption({ label: "English" });

  await expect(page.getByTestId("mark-grid")).toBeVisible();
  const columns = await page.locator('[data-testid^="mark-cell-0-"]').count();
  expect(columns).toBeGreaterThanOrEqual(10);

  // 15 marks typed from the keyboard: five columns, three students each, with
  // Enter saving and moving to the next row.
  for (let column = 0; column < 5; column += 1) {
    for (let row = 0; row < 3; row += 1) {
      const cell = page.getByTestId(`mark-cell-${row}-${column}`);
      await cell.focus();
      await page.keyboard.type(String(6 + column));
      await page.keyboard.press("Enter");
    }
  }

  // 15 marks pasted as a column: five more columns of three values.
  for (let column = 5; column < 10; column += 1) {
    const cell = page.getByTestId(`mark-cell-0-${column}`);
    await cell.focus();
    await cell.evaluate((element, text) => {
      const transfer = new DataTransfer();
      transfer.setData("text/plain", text);
      element.dispatchEvent(
        new ClipboardEvent("paste", {
          clipboardData: transfer,
          bubbles: true,
          cancelable: true,
        }),
      );
    }, "7\n8\n9");
  }

  await expect(page.getByTestId("mark-converted-0-0")).toHaveText("6");
  await expect(page.getByTestId("mark-converted-2-0")).toHaveText("6");
  await expect(page.getByTestId("mark-converted-2-9")).toHaveText("9");

  const stats = page.locator('[data-testid^="mark-stats-"]').first();
  await expect(stats).toContainText("3/3 entered");

  // The grid autosaves each cell; poll the API until all thirty marks are stored.
  const token = await apiLogin();
  await expect
    .poll(
      async () => {
        let entered = 0;
        for (const assessmentId of assessmentIds) {
          const sheet = await api<ScoreSheet>(
            token,
            `/api/v1/assessment/assessments/${assessmentId}/scores`,
          );
          entered += sheet.items.filter(
            (item) => item.raw_score !== null,
          ).length;
        }
        return entered;
      },
      { timeout: 90_000, intervals: [500, 1000, 2000] },
    )
    .toBe(30);
});
