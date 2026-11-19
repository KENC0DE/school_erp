import { fireEvent, render, waitFor } from "@testing-library/react-native";
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

import { SessionError } from "../src/session/session";
import type {
  AssessmentList,
  AssessmentSummary,
  MarkingWindow,
  ScoreBulkResult,
  ScoreItem,
  ScoreSheet,
  Submission,
} from "../src/assessment/types";

const mockPush = jest.fn();
let mockParams: Record<string, string> = {};
let mockPermissions: string[] = [];

jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
  useLocalSearchParams: () => mockParams,
}));

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
    user: { permissions: mockPermissions },
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

const mockCache = new Map<string, unknown>();

jest.mock("../src/storage/schoolStorage", () => ({
  forSchool: () => ({
    getCache: async (name: string) => mockCache.get(name) ?? null,
    setCache: async (name: string, value: unknown) => {
      mockCache.set(name, value);
    },
  }),
}));

const mockListAssessments = jest.fn();
const mockGetAssessment = jest.fn();
const mockGetScoreSheet = jest.fn();
const mockSaveScores = jest.fn();
const mockListWindows = jest.fn();
const mockListSubmissions = jest.fn();

jest.mock("../src/assessment/api", () => ({
  listAssessments: (...args: unknown[]) => mockListAssessments(...args),
  getAssessment: (...args: unknown[]) => mockGetAssessment(...args),
  getScoreSheet: (...args: unknown[]) => mockGetScoreSheet(...args),
  saveScores: (...args: unknown[]) => mockSaveScores(...args),
  listWindows: (...args: unknown[]) => mockListWindows(...args),
  listSubmissions: (...args: unknown[]) => mockListSubmissions(...args),
}));

const mockListYears = jest.fn();

jest.mock("../src/students/api", () => ({
  listYears: (...args: unknown[]) => mockListYears(...args),
}));

import AssessmentListScreen from "../app/(app)/assessment/index";
import MarkEntryScreen from "../app/(app)/assessment/[assessmentId]";
import { loadOutbox } from "../src/assessment/outbox";

const summary: AssessmentSummary = {
  id: "assessment-1",
  year_id: "year-1",
  year_code: "2025",
  term_id: "term-1",
  term_name: "Term 1",
  section_id: "section-1",
  section_code: "A",
  level_id: "level-1",
  level_name: "Grade 5",
  subject_id: "subject-1",
  subject_name: "Mathematics",
  component_key: "quizzes",
  component_name: "Quizzes",
  component_max_points: "20",
  title: "Quiz 1",
  assessment_date: "2025-10-01",
  out_of: "10",
  allow_bonus: false,
  status: "draft",
  scores: 2,
  entered: 1,
  row_version: 1,
};

function scoreItem(overrides: Partial<ScoreItem> = {}): ScoreItem {
  return {
    score_id: null,
    student_id: "student-1",
    student_number: "STU-0001",
    student_name: "Abebe Bekele",
    student_name_am: null,
    roll_number: "1",
    enrolled: true,
    raw_score: null,
    out_of: "10",
    status: "present",
    converted: null,
    note: null,
    row_version: null,
    entered_at: null,
    ...overrides,
  };
}

function buildSheet(items: ScoreItem[]): ScoreSheet {
  return {
    assessment_id: summary.id,
    title: summary.title,
    component_key: summary.component_key,
    component_max_points: summary.component_max_points,
    out_of: summary.out_of,
    allow_bonus: summary.allow_bonus,
    editable: true,
    items,
    stats: {
      total: items.length,
      entered: items.filter(
        (item) => item.status !== "present" || item.raw_score !== null,
      ).length,
      missing: 0,
      present: items.filter((item) => item.status === "present").length,
      absent: 0,
      excused: 0,
      exempt: 0,
      not_taken: 0,
      out_of: summary.out_of,
      component_max_points: summary.component_max_points,
      average_converted: null,
      average_percent: null,
      highest_converted: null,
      lowest_converted: null,
    },
  };
}

function bulkResult(items: ScoreItem[]): ScoreBulkResult {
  return { sheet: buildSheet(items), created: 0, updated: 1, unchanged: 0 };
}

const openWindow: MarkingWindow = {
  id: "window-1",
  year_id: "year-1",
  term_id: "term-1",
  level_id: null,
  section_id: "section-1",
  scope_key: "section:section-1",
  opens_at: "2025-09-01T00:00:00Z",
  closes_at: "2025-12-01T00:00:00Z",
  is_active: true,
  state: "open",
  note: null,
  row_version: 1,
};

const draftSubmission: Submission = {
  id: "submission-1",
  year_id: "year-1",
  term_id: "term-1",
  section_id: "section-1",
  section_code: "A",
  subject_id: "subject-1",
  subject_name: "Mathematics",
  status: "draft",
  submitted_at: null,
  approved_at: null,
  published_at: null,
  locked_at: null,
  note: null,
  assessments: 1,
  scores: 2,
  entered: 1,
  row_version: 1,
};

const twoStudents = [
  scoreItem(),
  scoreItem({
    student_id: "student-2",
    student_name: "Sara Mekonnen",
    roll_number: "2",
  }),
];

function networkError(): SessionError {
  return new SessionError("NETWORK_ERROR", "Cannot reach the school server");
}

function conflictError(): SessionError {
  return new SessionError(
    "CONFLICT",
    "The mark changed since it was loaded",
    409,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockCache.clear();
  mockParams = { assessmentId: summary.id };
  mockPermissions = ["assessment.view", "assessment.enter_marks"];

  mockListYears.mockResolvedValue({
    items: [{ id: "year-1", code: "2025", name: "2025/26", status: "active" }],
    total: 1,
    current_year_id: "year-1",
  });
  const list: AssessmentList = {
    items: [summary],
    next_cursor: null,
    total: 1,
  };
  mockListAssessments.mockResolvedValue(list);
  mockGetAssessment.mockResolvedValue(summary);
  mockGetScoreSheet.mockResolvedValue(buildSheet(twoStudents));
  mockSaveScores.mockResolvedValue(bulkResult(twoStudents));
  mockListWindows.mockResolvedValue({
    items: [openWindow],
    next_cursor: null,
    total: 1,
  });
  mockListSubmissions.mockResolvedValue({
    items: [draftSubmission],
    next_cursor: null,
    total: 1,
  });
});

describe("mobile assessment list", () => {
  it("lists the class assessments and opens mark entry", async () => {
    const view = await render(<AssessmentListScreen />);

    await waitFor(() => expect(view.getByText("Quiz 1")).toBeTruthy());
    expect(mockListYears).toHaveBeenCalledWith("school-alpha");
    expect(mockListAssessments).toHaveBeenCalledWith("school-alpha", "year-1");
    expect(view.getByText("1 entered")).toBeTruthy();

    await fireEvent.press(view.getByTestId("assessment-row-assessment-1"));
    expect(mockPush).toHaveBeenCalledWith({
      pathname: "/(app)/assessment/[assessmentId]",
      params: { assessmentId: "assessment-1" },
    });
  });

  it("refuses the screen without the assessment permission", async () => {
    mockPermissions = [];
    const view = await render(<AssessmentListScreen />);

    await waitFor(() =>
      expect(
        view.getByText("You do not have permission to enter marks."),
      ).toBeTruthy(),
    );
    expect(mockListAssessments).not.toHaveBeenCalled();
  });
});

describe("mobile mark entry", () => {
  it("shows the live converted mark and saves on enter with the row version", async () => {
    const view = await render(<MarkEntryScreen />);

    await waitFor(() => expect(view.getByText("Abebe Bekele")).toBeTruthy());
    expect(view.getByText("Card")).toBeTruthy();
    expect(view.getByText("List")).toBeTruthy();

    await fireEvent.changeText(view.getByTestId("mark-input-student-1"), "8");
    expect(view.getByTestId("mark-converted-student-1").props.children).toBe(
      "16",
    );

    await fireEvent(view.getByTestId("mark-input-student-1"), "submitEditing");

    await waitFor(() =>
      expect(mockSaveScores).toHaveBeenCalledWith(
        "school-alpha",
        "assessment-1",
        [
          {
            student_id: "student-1",
            raw_score: "8",
            status: "present",
            row_version: null,
          },
        ],
      ),
    );
    await waitFor(() => expect(view.getByText("Saved")).toBeTruthy());
  });

  it("keeps marks on the device when offline and syncs them once back online", async () => {
    mockSaveScores.mockRejectedValueOnce(networkError());
    const view = await render(<MarkEntryScreen />);

    await waitFor(() =>
      expect(view.getByTestId("mark-input-student-1")).toBeTruthy(),
    );
    await fireEvent.changeText(view.getByTestId("mark-input-student-1"), "9");
    await fireEvent(view.getByTestId("mark-input-student-1"), "submitEditing");

    await waitFor(() =>
      expect(view.getByTestId("mark-sync-student-1")).toBeTruthy(),
    );
    expect(view.getByText("Pending")).toBeTruthy();
    expect(view.getByText("Saved on this device.")).toBeTruthy();

    const queued = await loadOutbox("school-alpha");
    expect(queued).toHaveLength(1);
    expect(queued[0]).toMatchObject({
      student_id: "student-1",
      raw_score: "9",
    });

    mockSaveScores.mockResolvedValue(
      bulkResult([{ ...twoStudents[0]!, raw_score: "9" }]),
    );
    await fireEvent.press(view.getByLabelText("Sync now"));

    await waitFor(() => expect(view.getByText("Marks synced.")).toBeTruthy());
    expect(view.queryByTestId("mark-sync-student-1")).toBeNull();
    const remaining = await loadOutbox("school-alpha");
    expect(remaining).toHaveLength(0);
  });

  it("lists students in compact list mode", async () => {
    const view = await render(<MarkEntryScreen />);

    await waitFor(() => expect(view.getByText("Card")).toBeTruthy());
    await fireEvent.press(view.getByTestId("mark-mode-list"));
    expect(view.getByTestId("mark-input-student-2")).toBeTruthy();
    // Compact mode still shows status shortcuts for the keypad-free cases.
    expect(view.getByTestId("mark-status-student-2-absent")).toBeTruthy();
  });

  it("keeps the teacher's mark after a conflict by requeueing with the fresh version", async () => {
    mockSaveScores.mockRejectedValueOnce(conflictError());
    const view = await render(<MarkEntryScreen />);

    await waitFor(() =>
      expect(view.getByTestId("mark-input-student-1")).toBeTruthy(),
    );
    await fireEvent.changeText(view.getByTestId("mark-input-student-1"), "8");
    await fireEvent(view.getByTestId("mark-input-student-1"), "submitEditing");

    await waitFor(() =>
      expect(view.getByText("Resolve changed marks")).toBeTruthy(),
    );
    const serverItem = scoreItem({
      raw_score: "5",
      row_version: 2,
      score_id: "score-1",
    });
    mockGetScoreSheet.mockResolvedValue(
      buildSheet([serverItem, twoStudents[1]!]),
    );
    mockSaveScores.mockResolvedValue(
      bulkResult([{ ...serverItem, raw_score: "8", row_version: 3 }]),
    );

    await fireEvent.press(view.getByLabelText("Keep mine"));

    await waitFor(() =>
      expect(view.getByText("The mark was resolved.")).toBeTruthy(),
    );
    await waitFor(() =>
      expect(mockSaveScores).toHaveBeenLastCalledWith(
        "school-alpha",
        "assessment-1",
        [
          {
            student_id: "student-1",
            raw_score: "8",
            status: "present",
            row_version: 2,
          },
        ],
      ),
    );
    expect(view.queryByTestId("mark-conflict-student-1")).toBeNull();
  });

  it("accepts the server value after a conflict and reloads the row", async () => {
    mockSaveScores.mockRejectedValueOnce(conflictError());
    const view = await render(<MarkEntryScreen />);

    await waitFor(() =>
      expect(view.getByTestId("mark-input-student-1")).toBeTruthy(),
    );
    await fireEvent.changeText(view.getByTestId("mark-input-student-1"), "8");
    await fireEvent(view.getByTestId("mark-input-student-1"), "submitEditing");

    await waitFor(() =>
      expect(view.getByText("Resolve changed marks")).toBeTruthy(),
    );
    mockGetScoreSheet.mockResolvedValue(
      buildSheet([
        scoreItem({ raw_score: "5", row_version: 2, score_id: "score-1" }),
        twoStudents[1]!,
      ]),
    );

    await fireEvent.press(view.getByLabelText("Use server value"));

    await waitFor(() =>
      expect(view.getByText("The mark was resolved.")).toBeTruthy(),
    );
    expect(view.getByTestId("mark-input-student-1").props.value).toBe("5");
    expect(view.queryByTestId("mark-conflict-student-1")).toBeNull();
    const remaining = await loadOutbox("school-alpha");
    expect(remaining).toHaveLength(0);
  });

  it("makes a published term read-only", async () => {
    mockListSubmissions.mockResolvedValue({
      items: [{ ...draftSubmission, status: "published" }],
      next_cursor: null,
      total: 1,
    });
    const view = await render(<MarkEntryScreen />);

    await waitFor(() =>
      expect(
        view.getByText("Marks were published and are read-only."),
      ).toBeTruthy(),
    );
    expect(view.getByTestId("mark-input-student-1").props.editable).toBe(false);
  });
});
