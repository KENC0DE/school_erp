import {
  getStudent,
  listSections,
  listStudents,
  previewRegistration,
  registerStudent,
} from "../src/students/api";
import type { StudentRegistration } from "../src/students/types";

jest.mock("../src/storage/schoolStorage", () => ({
  forSchool: () => ({ getAccessToken: async () => "access-token" }),
  getVerifiedBaseUrl: async () => "https://school.example",
}));

const registration: StudentRegistration = {
  person: { given_name_en: "Abebe", father_name_en: "Bekele", grandfather_name_en: "Tesfaye" },
  enrollment: { year_id: "year-1", level_id: "level-1" },
};

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

describe("mobile students API", () => {
  beforeEach(() => {
    respond({});
  });

  it("reads a filtered, paged directory with the session token", async () => {
    respond({ items: [], next_cursor: null, total: 0 });
    await listStudents("school-alpha", { q: "Abebe", status: "active" }, "cursor-1");

    const [url, init] = lastCall();
    expect(url).toBe(
      "https://school.example/api/v1/students?q=Abebe&status=active&cursor=cursor-1&limit=25",
    );
    expect(init.method ?? "GET").toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer access-token");
  });

  it("reads one student profile", async () => {
    await getStudent("school-alpha", "student-1");
    expect(lastCall()[0]).toBe("https://school.example/api/v1/students/student-1");
  });

  it("previews a registration before saving", async () => {
    await previewRegistration("school-alpha", registration);
    const [url, init] = lastCall();
    expect(url).toBe("https://school.example/api/v1/students/register/preview");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(registration);
  });

  it("registers a student directly online", async () => {
    await registerStudent("school-alpha", registration);
    const [url, init] = lastCall();
    expect(url).toBe("https://school.example/api/v1/students");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(registration);
  });

  it("loads sections for the chosen year and level", async () => {
    await listSections("school-alpha", "year-1", "level-1");
    expect(lastCall()[0]).toBe(
      "https://school.example/api/v1/academics/sections?year_id=year-1&level_id=level-1",
    );
  });
});
