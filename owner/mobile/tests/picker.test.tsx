import { fireEvent, render, waitFor } from "@testing-library/react-native";

import SchoolPickerScreen from "../app/index";
import { DirectoryError } from "../src/directory/verify";

const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockResolveSchoolCode = jest.fn();

jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useLocalSearchParams: () => ({}),
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
    profile: null,
    profiles: [],
    user: null,
    locale: "en",
    mode: "light",
    activateProfile: jest.fn(),
    removeSavedProfile: jest.fn(),
    refreshProfiles: jest.fn(),
  }),
}));

jest.mock("../src/directory/client", () => ({
  resolveSchoolCode: (...args: unknown[]) => mockResolveSchoolCode(...args),
}));

describe("school picker", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockReplace.mockClear();
    mockResolveSchoolCode.mockReset();
  });

  it("shows the verification error and stays put when the directory signature is untrusted", async () => {
    mockResolveSchoolCode.mockRejectedValue(
      new DirectoryError("INVALID_SIGNATURE", "directory signature invalid"),
    );

    const { getByPlaceholderText, getByRole, getByText } = await render(<SchoolPickerScreen />);

    await fireEvent.changeText(getByPlaceholderText("DEMO or erpapp://school/DEMO"), "DEMO");
    await fireEvent.press(getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(getByText("The school directory response could not be verified.")).toBeTruthy(),
    );
    expect(mockResolveSchoolCode).toHaveBeenCalledWith("DEMO");
    expect(mockPush).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
