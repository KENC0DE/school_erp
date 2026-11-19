import { render, waitFor } from "@testing-library/react-native";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function readMessages(relativePath: string): Record<string, string> {
  return JSON.parse(
    readFileSync(resolve(__dirname, relativePath), "utf8"),
  ) as Record<string, string>;
}

const coreMessages = readMessages(
  "../../../school-erp/backend/core/i18n/en.json",
);
const assessmentMessages = readMessages(
  "../../../school-erp/backend/modules/assessment/i18n/en.json",
);

jest.mock("react-native-safe-area-context", () => {
  const { View } = jest.requireActual("react-native");
  return {
    SafeAreaView: View,
    SafeAreaProvider: View,
    useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
  };
});

jest.mock("../src/context/AppContext", () => ({
  useApp: () => ({
    ready: true,
    profile: {
      instanceId: "school-alpha",
      name: "Alpha Academy",
      apiBaseUrl: "https://school.example",
    },
    user: { permissions: ["assessment.view"], roles: ["parent"] },
    locale: "en",
    mode: "light",
  }),
}));

const messages: Record<string, string> = {
  ...coreMessages,
  ...Object.fromEntries(
    Object.entries(assessmentMessages).map(([key, value]) => [
      `assessment.${key}`,
      value,
    ]),
  ),
};

function mockTranslate(
  key: string,
  values?: Record<string, string | number>,
): string {
  const template = messages[key] ?? key;
  if (!values) return template;
  return template.replace(/\{\{(\w+)\}\}/g, (_match, name: string) =>
    name in values ? String(values[name]) : "",
  );
}

jest.mock("../src/i18n/SchoolI18nContext", () => ({
  useSchoolI18n: () => ({ t: mockTranslate, ready: true, reload: jest.fn() }),
}));

jest.mock("../src/theme/SchoolThemeContext", () => {
  const { defaultNativeTheme } = jest.requireActual("../src/theme/nativeTheme");
  return {
    useSchoolThemeContext: () => ({ rn: defaultNativeTheme("light") }),
  };
});

const mockListYears = jest.fn();
jest.mock("../src/students/api", () => ({
  listYears: (...args: unknown[]) => mockListYears(...args),
}));

const mockGetPortalResults = jest.fn();
jest.mock("../src/assessment/api", () => ({
  getPortalResults: (...args: unknown[]) => mockGetPortalResults(...args),
}));

import PortalResultsScreen from "../src/assessment/PortalResultsScreen";

const YEAR = { id: "year-1", code: "2026", name: "2026/27" };

function subject(overrides: Record<string, unknown> = {}) {
  return {
    subject_id: "sub-1",
    subject_name: "Mathematics",
    structure_id: "structure-1",
    structure_version: 1,
    scale_id: "scale-1",
    scale_version: 1,
    total: "35.69",
    out_of: "50",
    percent: "71.38",
    grade_label: "C",
    grade_remark: "Good",
    gpa_points: "2",
    is_pass: true,
    rank: 1,
    rank_size: 3,
    status: "published",
    terms: null,
    ...overrides,
  };
}

function result(overrides: Record<string, unknown> = {}) {
  return {
    snapshot_id: "snap-1",
    kind: "term",
    year_id: "year-1",
    year_code: "2026",
    term_id: "term-1",
    term_name: "Semester 1",
    section_id: "sec-1",
    section_code: "G5A",
    level_name: "Grade 5",
    published_at: "2026-11-15T09:00:00Z",
    result: {
      student_id: "stu-1",
      student_number: "STU-2026-0001",
      student_name: "Abel Bekele",
      student_name_am: null,
      roll_number: "1",
      subjects: [subject()],
      total: "35.69",
      out_of: "50",
      percent: "71.38",
      grade_label: "C",
      grade_remark: "Good",
      gpa_points: "2",
      is_pass: true,
      rank: 1,
      rank_size: 3,
      status: "published",
    },
    ...overrides,
  };
}

function child(overrides: Record<string, unknown> = {}) {
  return {
    student_id: "stu-1",
    student_number: "STU-2026-0001",
    student_name: "Abel Bekele",
    student_name_am: null,
    results: [result()],
    ...overrides,
  };
}

beforeEach(() => {
  mockListYears.mockResolvedValue({
    items: [YEAR],
    total: 1,
    current_year_id: "year-1",
  });
  mockGetPortalResults.mockResolvedValue({ children: [] });
});

afterEach(() => {
  jest.clearAllMocks();
});

describe("mobile portal results", () => {
  it("shows each linked child with the published subject marks", async () => {
    mockGetPortalResults.mockResolvedValue({
      children: [
        child(),
        child({
          student_id: "stu-2",
          student_number: "STU-2026-0002",
          student_name: "Sara Tesfaye",
        }),
      ],
    });

    const view = await render(<PortalResultsScreen />);

    await waitFor(() => expect(view.getByText("Abel Bekele")).toBeTruthy());
    expect(view.getByText("Sara Tesfaye")).toBeTruthy();
    expect(view.getByText("STU-2026-0002")).toBeTruthy();
    expect(view.getAllByText("Semester 1 result")).toHaveLength(2);
    expect(view.getAllByText("Mathematics")).toHaveLength(2);
    expect(view.getAllByText("35.69 of 50 · 71.38% · 1/3").length).toBe(2);
    expect(view.getAllByText("Pass").length).toBe(2);
    expect(mockGetPortalResults).toHaveBeenCalledWith("school-alpha", "year-1");
  });

  it("shows the year result without a term", async () => {
    mockGetPortalResults.mockResolvedValue({
      children: [
        child({
          results: [
            result({
              kind: "year",
              term_id: null,
              term_name: null,
            }),
          ],
        }),
      ],
    });

    const view = await render(<PortalResultsScreen />);

    await waitFor(() => expect(view.getByText("Year result")).toBeTruthy());
  });

  it("explains that nothing appears before publication", async () => {
    const view = await render(<PortalResultsScreen />);

    await waitFor(() =>
      expect(view.getByText("No published results yet")).toBeTruthy(),
    );
    expect(
      view.getByText(
        "When the school publishes marks, they appear here for you.",
      ),
    ).toBeTruthy();
  });
});
