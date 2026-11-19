import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function readMessages(relativePath: string): Record<string, string> {
  return JSON.parse(readFileSync(resolve(__dirname, relativePath), "utf8")) as Record<
    string,
    string
  >;
}

const coreMessages = readMessages("../../../school-erp/backend/core/i18n/en.json");
const attendanceMessages = readMessages(
  "../../../school-erp/backend/modules/attendance/i18n/en.json",
);

const mockPush = jest.fn();
const mockReplace = jest.fn();
let mockParams: Record<string, string> = {};
let mockPermissions: string[] = [];

jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
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
    Object.entries(attendanceMessages).map(([key, value]) => [`attendance.${key}`, value]),
  ),
};

function mockTranslate(key: string, values?: Record<string, string | number>): string {
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

const mockListSessions = jest.fn();
const mockGetSession = jest.fn();
const mockCreateSession = jest.fn();
const mockSaveRecords = jest.fn();
const mockSubmitSession = jest.fn();
jest.mock("../src/attendance/api", () => ({
  listSessions: (...args: unknown[]) => mockListSessions(...args),
  getSession: (...args: unknown[]) => mockGetSession(...args),
  createSession: (...args: unknown[]) => mockCreateSession(...args),
  saveRecords: (...args: unknown[]) => mockSaveRecords(...args),
  submitSession: (...args: unknown[]) => mockSubmitSession(...args),
}));

const mockLoadOutbox = jest.fn();
const mockFlushOutbox = jest.fn();
const mockSaveOrQueue = jest.fn();
jest.mock("../src/attendance/outbox", () => ({
  loadOutbox: (...args: unknown[]) => mockLoadOutbox(...args),
  flushOutbox: (...args: unknown[]) => mockFlushOutbox(...args),
  saveOrQueue: (...args: unknown[]) => mockSaveOrQueue(...args),
}));

const mockListYears = jest.fn();
const mockListLevels = jest.fn();
const mockListSections = jest.fn();
jest.mock("../src/students/api", () => ({
  listYears: (...args: unknown[]) => mockListYears(...args),
  listLevels: (...args: unknown[]) => mockListLevels(...args),
  listSections: (...args: unknown[]) => mockListSections(...args),
}));

import AttendanceScreen from "../app/(app)/attendance/index";
import AttendanceSessionScreen from "../app/(app)/attendance/[sessionId]";

const SESSION = {
  id: "session-1",
  year_id: "year-1",
  year_code: "2026",
  section_id: "section-1",
  section_code: "A",
  section_name: "Grade 5 A",
  level_id: "level-1",
  level_code: "g5",
  level_name: "Grade 5",
  date: "2026-10-01",
  mode: "daily" as const,
  period: null,
  subject_id: null,
  subject_code: null,
  subject_name: null,
  status: "open" as const,
  notes: null,
  counts: { total: 3, present: 3, absent: 0, late: 0, excused: 0 },
  status_changed_at: null,
  status_changed_by: null,
  status_changed_by_name: null,
  row_version: 1,
};

const DETAIL = {
  ...SESSION,
  records: [
    {
      id: "record-1",
      session_id: "session-1",
      student_id: "student-1",
      student_number: "S-1",
      student_name: "Abebe Bekele Tesfaye",
      student_name_am: null,
      roll_number: "1",
      status: "present" as const,
      reason: null,
      late_minutes: null,
      note: null,
      recorded_at: "2026-10-01T08:00:00Z",
      recorded_by: "u-1",
      recorded_by_name: "Attendance Lead",
      row_version: 1,
    },
  ],
  roster: [
    {
      student_id: "student-1",
      student_number: "S-1",
      full_name: "Abebe Bekele Tesfaye",
      roll_number: "1",
      status: "present" as const,
      record_id: "record-1",
    },
  ],
};

beforeEach(() => {
  mockPush.mockReset();
  mockReplace.mockReset();
  mockParams = { sessionId: "session-1" };
  mockPermissions = ["attendance.view", "attendance.record"];
  mockListSessions.mockResolvedValue({ items: [SESSION], next_cursor: null, total: 1 });
  mockGetSession.mockResolvedValue(DETAIL);
  mockCreateSession.mockResolvedValue({ ...DETAIL, id: "session-2" });
  mockSaveRecords.mockResolvedValue(DETAIL);
  mockSubmitSession.mockResolvedValue({ ...DETAIL, status: "submitted" });
  mockLoadOutbox.mockResolvedValue([]);
  mockFlushOutbox.mockResolvedValue({ sent: 0, pending: 0 });
  mockSaveOrQueue.mockResolvedValue({ detail: DETAIL, queued: 0 });
  mockListYears.mockResolvedValue({
    items: [
      { id: "year-1", code: "2026", name: "2026/27", status: "open" },
    ],
    total: 1,
    current_year_id: "year-1",
  });
  mockListLevels.mockResolvedValue({
    items: [{ id: "level-1", code: "g5", name: "Grade 5", in_scope: true }],
    total: 1,
  });
  mockListSections.mockResolvedValue({
    items: [
      {
        id: "section-1",
        year_id: "year-1",
        level_id: "level-1",
        code: "A",
        name: "Grade 5 A",
        is_active: true,
      },
    ],
    total: 1,
  });
});

describe("mobile attendance", () => {
  it("lists the day's registers and opens one", async () => {
    const screen = await render(<AttendanceScreen />);
    await waitFor(() => expect(screen.getByText("Grade 5 · Grade 5 A")).toBeTruthy());
    fireEvent.press(screen.getByTestId("attendance-row-session-1"));
    expect(mockPush).toHaveBeenCalledWith({
      pathname: "/(app)/attendance/[sessionId]",
      params: { sessionId: "session-1" },
    });
  });

  it("opens a register for the selected section", async () => {
    const screen = await render(<AttendanceScreen />);
    await waitFor(() => expect(screen.getByTestId("attendance-section")).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByTestId("attendance-section").props.accessibilityValue.text).toBe(
        "Grade 5 A",
      ),
    );
    fireEvent.press(screen.getByText("Open the register"));
    await waitFor(() => expect(mockCreateSession).toHaveBeenCalled());
    expect(mockCreateSession).toHaveBeenCalledWith(
      "school-alpha",
      expect.objectContaining({
        year_id: "year-1",
        section_id: "section-1",
        date: expect.any(String),
      }),
    );
  });

  it("marks an exception and saves it with the roster grid", async () => {
    const screen = await render(<AttendanceSessionScreen />);
    await waitFor(() => expect(screen.getByText("Abebe Bekele Tesfaye")).toBeTruthy());

    fireEvent.press(screen.getByTestId("attendance-status-student-1-absent"));
    await waitFor(() =>
      expect(screen.getByTestId("attendance-reason-student-1")).toBeTruthy(),
    );
    fireEvent.changeText(screen.getByTestId("attendance-reason-student-1"), "Family matter");
    await waitFor(() =>
      expect(screen.getByTestId("attendance-reason-student-1").props.value).toBe(
        "Family matter",
      ),
    );
    fireEvent.press(screen.getByText("Save"));

    await waitFor(() => expect(mockSaveOrQueue).toHaveBeenCalled());
    expect(mockSaveOrQueue).toHaveBeenCalledWith(
      "school-alpha",
      "session-1",
      [
        expect.objectContaining({
          student_id: "student-1",
          status: "absent",
          reason: "Family matter",
        }),
      ],
    );
    await waitFor(() => expect(screen.getByText("Attendance saved.")).toBeTruthy());
  });

  it("queues an offline entry and syncs it when the connection returns", async () => {
    mockSaveOrQueue.mockResolvedValueOnce({ detail: null, queued: 1 });
    const screen = await render(<AttendanceSessionScreen />);
    await waitFor(() => expect(screen.getByText("Abebe Bekele Tesfaye")).toBeTruthy());

    fireEvent.press(screen.getByTestId("attendance-status-student-1-absent"));
    await waitFor(() =>
      expect(screen.getByTestId("attendance-reason-student-1")).toBeTruthy(),
    );
    fireEvent.press(screen.getByText("Save"));
    await waitFor(() => expect(screen.getByText("Saved on this device")).toBeTruthy());
    expect(screen.getByText("1 entries waiting to sync.")).toBeTruthy();

    mockFlushOutbox.mockResolvedValueOnce({ sent: 1, pending: 0 });
    fireEvent.press(screen.getAllByText("Sync now")[0]!);
    await waitFor(() => expect(mockFlushOutbox).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("Attendance synced.")).toBeTruthy());
    expect(screen.queryByText("1 entries waiting to sync.")).toBeNull();
  });
});
