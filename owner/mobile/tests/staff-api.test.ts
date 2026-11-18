import { getStaff, listStaff } from "../src/staff/api";

jest.mock("../src/storage/schoolStorage", () => ({
  forSchool: () => ({ getAccessToken: async () => "access-token" }),
  getVerifiedBaseUrl: async () => "https://school.example",
}));

function respond(payload: unknown): void {
  global.fetch = jest.fn(
    async () =>
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  ) as unknown as typeof fetch;
}

function lastCall(): [string, RequestInit] {
  return (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
}

describe("mobile staff API", () => {
  beforeEach(() => {
    respond({});
  });

  it("reads a filtered, paged staff directory with the session token", async () => {
    respond({ items: [], next_cursor: null, total: 0 });
    await listStaff("school-alpha", { q: "Abebe", status: "active" }, "cursor-1");

    const [url, init] = lastCall();
    expect(url).toBe(
      "https://school.example/api/v1/staff?q=Abebe&status=active&cursor=cursor-1&limit=25",
    );
    expect(init.method ?? "GET").toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer access-token");
  });

  it("reads one staff profile", async () => {
    await getStaff("school-alpha", "staff-1");
    expect(lastCall()[0]).toBe("https://school.example/api/v1/staff/staff-1");
  });
});
