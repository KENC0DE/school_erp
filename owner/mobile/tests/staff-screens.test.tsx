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
const staffMessages = readMessages("../../../school-erp/backend/modules/staff/i18n/en.json");
import type { StaffDetail, StaffSummary } from "../src/staff/types";

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
    Object.entries(staffMessages).map(([key, value]) => [`staff.${key}`, value]),
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

const mockListStaff = jest.fn();
const mockGetStaff = jest.fn();

jest.mock("../src/staff/api", () => ({
  listStaff: (...args: unknown[]) => mockListStaff(...args),
  getStaff: (...args: unknown[]) => mockGetStaff(...args),
}));

import StaffScreen from "../app/(app)/staff/index";
import StaffProfileScreen from "../app/(app)/staff/[staffId]";

const person = {
  id: "person-1",
  given_name_en: "Abebe",
  father_name_en: "Bekele",
  grandfather_name_en: "Tesfaye",
  given_name_am: "አበበ",
  father_name_am: "በቀለ",
  grandfather_name_am: "ተስፋዬ",
  sex: "male",
  date_of_birth: "1985-04-12",
  phone: "0911000000",
  email: "abebe@demo.school",
  address: "Addis Ababa",
  full_name: "Abebe Bekele Tesfaye",
  short_name: "Abebe Bekele",
  row_version: 1,
};

const staff: StaffSummary = {
  id: "staff-1",
  staff_number: "STF-2026-0001",
  status: "active",
  person,
  user_id: null,
  department: {
    id: "dept-1",
    code: "science",
    name: "Science",
    name_am: null,
    is_active: true,
  },
  position: {
    id: "position-1",
    code: "teacher",
    name: "Teacher",
    name_am: null,
    department_id: "dept-1",
    is_teaching: true,
    is_active: true,
  },
  hire_date: "2020-09-01",
  end_date: null,
  row_version: 1,
};

const detail: StaffDetail = {
  ...staff,
  notes: "Head of science.",
};

beforeEach(() => {
  jest.clearAllMocks();
  mockParams = {};
  mockPermissions = ["staff.view"];
  mockListStaff.mockResolvedValue({
    items: [staff],
    next_cursor: null,
    total: 1,
  });
  mockGetStaff.mockResolvedValue(detail);
});

describe("mobile staff directory", () => {
  it("lists staff from the selected school and opens a profile", async () => {
    const view = await render(<StaffScreen />);

    await waitFor(() => expect(view.getByText("Abebe Bekele Tesfaye")).toBeTruthy());
    expect(mockListStaff).toHaveBeenCalledWith("school-alpha", {}, null);
    expect(view.getByText("STF-2026-0001 · Science · Teacher")).toBeTruthy();
    expect(view.getByText("Active")).toBeTruthy();

    await fireEvent.press(view.getByText("Abebe Bekele Tesfaye"));
    expect(mockPush).toHaveBeenCalledWith({
      pathname: "/(app)/staff/[staffId]",
      params: { staffId: "staff-1" },
    });
  });

  it("searches by name and status", async () => {
    const view = await render(<StaffScreen />);
    await waitFor(() => expect(view.getByText("Abebe Bekele Tesfaye")).toBeTruthy());

    await fireEvent.changeText(view.getByTestId("staff-search"), "Abebe");
    await fireEvent.press(view.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(mockListStaff).toHaveBeenLastCalledWith(
        "school-alpha",
        { q: "Abebe", status: undefined },
        null,
      ),
    );
  });

  it("shows the empty state when there are no staff", async () => {
    mockListStaff.mockResolvedValue({ items: [], next_cursor: null, total: 0 });
    const view = await render(<StaffScreen />);

    await waitFor(() => expect(view.getByText("No staff yet")).toBeTruthy());
    expect(view.getByText("Add the first staff member to get started.")).toBeTruthy();
  });

  it("denies the directory without the staff permission", async () => {
    mockPermissions = ["students.view"];
    const view = await render(<StaffScreen />);

    await waitFor(() =>
      expect(
        view.getByText("You do not have permission to see staff records."),
      ).toBeTruthy(),
    );
    expect(mockListStaff).not.toHaveBeenCalled();
  });
});

describe("mobile staff profile", () => {
  it("shows the contact and employment details", async () => {
    mockParams = { staffId: "staff-1" };
    const view = await render(<StaffProfileScreen />);

    await waitFor(() => expect(mockGetStaff).toHaveBeenCalledWith("school-alpha", "staff-1"));
    expect(view.getByText("STF-2026-0001")).toBeTruthy();
    expect(view.getByText("Science")).toBeTruthy();
    expect(view.getByText("Teacher")).toBeTruthy();
    expect(view.getByText("0911000000")).toBeTruthy();
    expect(view.getByText("abebe@demo.school")).toBeTruthy();
    expect(view.getByText("Head of science.")).toBeTruthy();
  });

  it("returns to the directory", async () => {
    mockParams = { staffId: "staff-1" };
    const view = await render(<StaffProfileScreen />);
    await waitFor(() => expect(mockGetStaff).toHaveBeenCalled());

    await fireEvent.press(view.getByText("Back to staff"));
    expect(mockPush).toHaveBeenCalledWith("/(app)/staff");
  });
});
