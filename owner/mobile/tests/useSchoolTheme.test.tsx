import { DEFAULT_THEME } from "@erp/tokens";
import { renderHook, waitFor } from "@testing-library/react-native";

import type { VerifiedProfile } from "../src/directory/types";
import { useSchoolTheme } from "../src/theme/useSchoolTheme";

let mockToken: string | null = null;
let mockCached: unknown = null;
const mockSetCache = jest.fn(async (_key: string, value: unknown) => {
  mockCached = value;
});

jest.mock("../src/storage/schoolStorage", () => ({
  forSchool: () => ({
    getCache: async () => mockCached,
    setCache: (key: string, value: unknown) => mockSetCache(key, value),
    getAccessToken: async () => mockToken,
  }),
  getVerifiedBaseUrl: async () => "https://school.example",
}));

const profile = {
  instanceId: "school-alpha",
  name: "Alpha Academy",
  apiBaseUrl: "https://school.example",
} as VerifiedProfile;

describe("useSchoolTheme", () => {
  beforeEach(() => {
    mockToken = null;
    mockCached = null;
    mockSetCache.mockClear();
    global.fetch = jest.fn(async () =>
      new Response(
        JSON.stringify({
          key: "ocean",
          name: "Ocean",
          tokens: DEFAULT_THEME.tokens,
          source: "user",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
  });

  it("sends the session token so the backend resolves the user's own theme", async () => {
    mockToken = "access-token";
    const { result } = await renderHook(() => useSchoolTheme(profile, "dark"));

    await waitFor(() => expect(result.current.source).toBe("user"));
    expect(global.fetch).toHaveBeenCalledWith(
      "https://school.example/api/v1/themes/active",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer access-token" }),
      }),
    );
    expect(result.current.theme.key).toBe("ocean");
    expect(result.current.rn.colors.background).toBeTruthy();
  });

  it("loads the public school theme before sign-in and caches it", async () => {
    global.fetch = jest.fn(async () =>
      new Response(
        JSON.stringify({
          key: "ocean",
          name: "Ocean",
          tokens: DEFAULT_THEME.tokens,
          source: "instance",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    const { result } = await renderHook(() => useSchoolTheme(profile, "light"));

    await waitFor(() => expect(result.current.source).toBe("school"));
    const headers = (global.fetch as jest.Mock).mock.calls[0][1].headers;
    expect(headers.Authorization).toBeUndefined();
    expect(result.current.theme.key).toBe("ocean");
    expect(mockSetCache).toHaveBeenCalledWith("theme", expect.objectContaining({ key: "ocean" }));
  });

  it("falls back to the shipped theme when the school theme is unreadable", async () => {
    mockCached = null;
    global.fetch = jest.fn(async () =>
      new Response(JSON.stringify({ key: "broken", name: "Broken", tokens: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
    const { result } = await renderHook(() => useSchoolTheme(profile, "light"));

    await waitFor(() => expect(result.current.source).toBe("default"));
    expect(result.current.theme.key).toBe(DEFAULT_THEME.key);
    expect(result.current.rn.colors.background).toBeTruthy();
  });
});
