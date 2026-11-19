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
const studentMessages = readMessages("../../../school-erp/backend/modules/students/i18n/en.json");
import { SessionError } from "../src/session/session";
import type { StudentDetail, StudentSummary } from "../src/students/types";

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
    Object.entries(studentMessages).map(([key, value]) => [`students.${key}`, value]),
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

const mockListStudents = jest.fn();
const mockGetStudent = jest.fn();
const mockPreviewRegistration = jest.fn();
const mockRegisterStudent = jest.fn();
const mockListYears = jest.fn();
const mockListLevels = jest.fn();
const mockListSections = jest.fn();

jest.mock("../src/students/api", () => ({
  listStudents: (...args: unknown[]) => mockListStudents(...args),
  getStudent: (...args: unknown[]) => mockGetStudent(...args),
  previewRegistration: (...args: unknown[]) => mockPreviewRegistration(...args),
  registerStudent: (...args: unknown[]) => mockRegisterStudent(...args),
  listYears: (...args: unknown[]) => mockListYears(...args),
  listLevels: (...args: unknown[]) => mockListLevels(...args),
  listSections: (...args: unknown[]) => mockListSections(...args),
}));

import StudentsScreen from "../app/(app)/students/index";
import StudentProfileScreen from "../app/(app)/students/[studentId]";
import StudentRegistrationScreen from "../app/(app)/students/new";

const person = {
  id: "person-1",
  given_name_en: "Abebe",
  father_name_en: "Bekele",
  grandfather_name_en: "Tesfaye",
  given_name_am: "አበበ",
  father_name_am: "በቀለ",
  grandfather_name_am: "ተስፋዬ",
  sex: "male",
  date_of_birth: "2015-01-01",
  phone: "0911000000",
  email: null,
  address: "Addis Ababa",
  full_name: "Abebe Bekele Tesfaye",
  short_name: "Abebe Bekele",
  row_version: 1,
};

const enrollment = {
  id: "enrollment-1",
  student_id: "student-1",
  year_id: "year-1",
  year_code: "2025",
  year_name: "2025/26",
  level_id: "level-1",
  level_code: "G1",
  level_name: "Grade 1",
  section_id: "section-1",
  section_code: "A",
  roll_number: "1",
  status: "active" as const,
  row_version: 1,
};

const student: StudentSummary = {
  id: "student-1",
  student_number: "STU-0001",
  status: "active",
  admission_date: "2025-09-01",
  person,
  enrollment,
  row_version: 1,
};

const detail: StudentDetail = {
  ...student,
  exit_date: null,
  exit_reason: null,
  notes: null,
  enrollments: [enrollment],
  guardians: [
    {
      id: "guardian-1",
      relationship: "mother",
      is_primary: true,
      can_pickup: true,
      person: {
        ...person,
        id: "person-2",
        sex: "female",
        given_name_en: "Marta",
        father_name_en: "Alemu",
        grandfather_name_en: "Kebede",
        full_name: "Marta Alemu Kebede",
        short_name: "Marta Alemu",
      },
    },
  ],
  medical: {
    blood_type: "O+",
    allergies: "Peanuts",
    chronic_conditions: null,
    medications: null,
    emergency_contact_name: "Marta",
    emergency_contact_phone: "0911222222",
    consent_to_treat: false,
  },
};

async function fillLatinNames(view: Awaited<ReturnType<typeof render>>): Promise<void> {
  await fireEvent.changeText(view.getByTestId("name-given_name_en"), "Abebe");
  await fireEvent.changeText(view.getByTestId("name-father_name_en"), "Bekele");
  await fireEvent.changeText(view.getByTestId("name-grandfather_name_en"), "Tesfaye");
}

beforeEach(() => {
  jest.clearAllMocks();
  mockParams = {};
  mockPermissions = ["students.view", "students.manage", "students.medical.view"];
  mockListStudents.mockResolvedValue({
    items: [student],
    next_cursor: null,
    total: 1,
  });
  mockGetStudent.mockResolvedValue(detail);
  mockListYears.mockResolvedValue({
    items: [{ id: "year-1", code: "2025", name: "2025/26", status: "active" }],
    total: 1,
    current_year_id: "year-1",
  });
  mockListLevels.mockResolvedValue({
    items: [{ id: "level-1", code: "G1", name: "Grade 1", in_scope: true }],
    total: 1,
  });
  mockListSections.mockResolvedValue({ items: [], total: 0 });
  mockPreviewRegistration.mockResolvedValue({
    student_number: "STU-0002",
    number_generated: true,
    full_name: "Abebe Bekele Tesfaye",
    duplicate_warnings: [],
    has_enrollment: false,
  });
  mockRegisterStudent.mockResolvedValue({ ...student, id: "student-2" });
});

describe("mobile student directory", () => {
  it("lists students from the selected school and opens a profile", async () => {
    const view = await render(<StudentsScreen />);

    await waitFor(() => expect(view.getByText("Abebe Bekele Tesfaye")).toBeTruthy());
    expect(mockListStudents).toHaveBeenCalledWith("school-alpha", {}, null);
    expect(view.getByText("STU-0001 · Grade 1 · A")).toBeTruthy();
    expect(view.getByText("Active")).toBeTruthy();

    await fireEvent.press(view.getByTestId("student-row-student-1"));
    expect(mockPush).toHaveBeenCalledWith({
      pathname: "/(app)/students/[studentId]",
      params: { studentId: "student-1" },
    });
  });

  it("shows the empty state when there are no students", async () => {
    mockListStudents.mockResolvedValue({
      items: [],
      next_cursor: null,
      total: 0,
    });
    const view = await render(<StudentsScreen />);

    await waitFor(() => expect(view.getByText("No students yet")).toBeTruthy());
    expect(view.getByText("Register the first student to get started.")).toBeTruthy();
  });

  it("shows a permission error without calling the API", async () => {
    mockPermissions = [];
    const view = await render(<StudentsScreen />);

    await waitFor(() =>
      expect(view.getByText("You do not have permission to view student records.")).toBeTruthy(),
    );
    expect(mockListStudents).not.toHaveBeenCalled();
  });

  it("shows a network error and retries the directory", async () => {
    mockListStudents.mockRejectedValueOnce(new SessionError("NETWORK_ERROR", "offline"));
    const view = await render(<StudentsScreen />);

    await waitFor(() =>
      expect(view.getByText("Cannot reach the school server. Check your connection.")).toBeTruthy(),
    );
    await fireEvent.press(view.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(view.getByText("Abebe Bekele Tesfaye")).toBeTruthy());
    expect(mockListStudents).toHaveBeenCalledTimes(2);
  });

  it("searches with the entered name as a filtered request", async () => {
    const view = await render(<StudentsScreen />);
    await waitFor(() => expect(mockListStudents).toHaveBeenCalledTimes(1));

    await fireEvent.changeText(view.getByTestId("students-search"), "Abebe");
    await fireEvent.press(view.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(mockListStudents).toHaveBeenLastCalledWith(
        "school-alpha",
        { q: "Abebe", status: undefined },
        null,
      ),
    );
  });
});

describe("mobile student profile", () => {
  it("hides medical records without the medical permission", async () => {
    mockParams = { studentId: "student-1" };
    mockPermissions = ["students.view"];
    const view = await render(<StudentProfileScreen />);

    await waitFor(() => expect(view.getByText("Abebe Bekele Tesfaye")).toBeTruthy());
    expect(view.getByText("Marta Alemu Kebede")).toBeTruthy();
    expect(view.queryByText("Medical record")).toBeNull();
    expect(view.queryByText("O+")).toBeNull();
    expect(mockGetStudent).toHaveBeenCalledWith("school-alpha", "student-1");
  });

  it("shows medical records to a user with the medical permission", async () => {
    mockParams = { studentId: "student-1" };
    mockPermissions = ["students.view", "students.medical.view"];
    const view = await render(<StudentProfileScreen />);

    await waitFor(() => expect(view.getByText("Medical record")).toBeTruthy());
    expect(view.getByText("O+")).toBeTruthy();
    expect(view.getByText("Peanuts")).toBeTruthy();
  });

  it("requires the students view permission", async () => {
    mockParams = { studentId: "student-1" };
    mockPermissions = [];
    const view = await render(<StudentProfileScreen />);

    await waitFor(() =>
      expect(view.getByText("You do not have permission to view student records.")).toBeTruthy(),
    );
    expect(mockGetStudent).not.toHaveBeenCalled();
  });

  it("shows a profile error with retry", async () => {
    mockParams = { studentId: "student-1" };
    mockGetStudent.mockRejectedValueOnce(new SessionError("NETWORK_ERROR", "offline"));
    const view = await render(<StudentProfileScreen />);

    await waitFor(() =>
      expect(view.getByText("Cannot reach the school server. Check your connection.")).toBeTruthy(),
    );
    await fireEvent.press(view.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(view.getByText("Abebe Bekele Tesfaye")).toBeTruthy());
  });
});

describe("mobile student registration", () => {
  it("requires the students manage permission", async () => {
    mockPermissions = ["students.view"];
    const view = await render(<StudentRegistrationScreen />);

    await waitFor(() =>
      expect(view.getByText("You do not have permission to register students.")).toBeTruthy(),
    );
    expect(mockListYears).not.toHaveBeenCalled();
  });

  it("rejects an incomplete name script before calling the API", async () => {
    const view = await render(<StudentRegistrationScreen />);
    await fireEvent.changeText(view.getByTestId("name-given_name_en"), "Abebe");
    await fireEvent.press(view.getByRole("button", { name: "Register student" }));

    await waitFor(() =>
      expect(
        view.getByText(
          "Enter at least one complete name script: given, father and grandfather names.",
        ),
      ).toBeTruthy(),
    );
    expect(mockPreviewRegistration).not.toHaveBeenCalled();
  });

  it("previews, warns about duplicates, and only saves after confirmation", async () => {
    mockPreviewRegistration.mockResolvedValue({
      student_number: "STU-0002",
      number_generated: true,
      full_name: "Abebe Bekele Tesfaye",
      duplicate_warnings: [
        {
          person: { full_name: "Abebe Bekele Tesfaye" },
          reason: "same_names_and_dob",
          similarity: 1,
        },
      ],
      has_enrollment: false,
    });
    const view = await render(<StudentRegistrationScreen />);
    await fillLatinNames(view);
    await fireEvent.press(view.getByRole("button", { name: "Register student" }));

    await waitFor(() => expect(view.getByTestId("registration-duplicates")).toBeTruthy());
    expect(view.getByText("Possible duplicate")).toBeTruthy();
    expect(view.getByText(/100% similar/)).toBeTruthy();
    expect(view.getByText("The next free student number is STU-0002.")).toBeTruthy();
    expect(mockRegisterStudent).not.toHaveBeenCalled();

    await fireEvent.press(view.getByRole("button", { name: "Register anyway" }));
    await waitFor(() => expect(mockRegisterStudent).toHaveBeenCalledTimes(1));
    expect(mockPreviewRegistration).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith({
      pathname: "/(app)/students/[studentId]",
      params: { studentId: "student-2" },
    });
  });

  it("registers directly when the preview finds no duplicates", async () => {
    const view = await render(<StudentRegistrationScreen />);
    await fillLatinNames(view);
    await fireEvent.press(view.getByRole("button", { name: "Register student" }));

    await waitFor(() => expect(mockRegisterStudent).toHaveBeenCalledTimes(1));
    expect(mockPreviewRegistration).toHaveBeenCalledWith(
      "school-alpha",
      expect.objectContaining({
        person: expect.objectContaining({ given_name_en: "Abebe" }),
      }),
    );
    expect(mockReplace).toHaveBeenCalledWith({
      pathname: "/(app)/students/[studentId]",
      params: { studentId: "student-2" },
    });
  });

  it("requires both a year and a level when an enrollment is started", async () => {
    const view = await render(<StudentRegistrationScreen />);
    await fillLatinNames(view);
    await waitFor(() => expect(mockListYears).toHaveBeenCalled());
    await fireEvent.press(view.getByTestId("register-year"));
    await fireEvent.press(view.getByTestId("register-year-option-year-1"));
    await fireEvent.press(view.getByRole("button", { name: "Register student" }));

    await waitFor(() =>
      expect(
        view.getByText(
          "Choose both an academic year and a grade level, or leave the enrollment empty.",
        ),
      ).toBeTruthy(),
    );
    expect(mockPreviewRegistration).not.toHaveBeenCalled();
  });

  it("surfaces an online-only network failure without queueing", async () => {
    mockPreviewRegistration.mockRejectedValue(new SessionError("NETWORK_ERROR", "offline"));
    const view = await render(<StudentRegistrationScreen />);
    await fillLatinNames(view);
    await fireEvent.press(view.getByRole("button", { name: "Register student" }));

    await waitFor(() =>
      expect(view.getByText("Cannot reach the school server. Check your connection.")).toBeTruthy(),
    );
    expect(mockRegisterStudent).not.toHaveBeenCalled();
  });
});
