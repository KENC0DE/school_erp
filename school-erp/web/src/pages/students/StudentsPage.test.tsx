import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "../../App";

interface MockRequest {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}

const messages: Record<string, string> = {
  "app.name": "School ERP",
  "app.short_name": "SE",
  "nav.dashboard": "Dashboard",
  "nav.students": "Students",
  "auth.logout": "Sign out",
  "common.loading": "Loading…",
  "common.cancel": "Cancel",
  "common.save": "Save",
  "common.retry": "Retry",
  "common.request_id": "Request id",
  "common.close": "Close",
  "common.yes": "Yes",
  "common.no": "No",
  "name.title": "Full name",
  "name.latin": "Latin script",
  "name.amharic": "Amharic script",
  "name.given": "Given name",
  "name.father": "Father's name",
  "name.grandfather": "Grandfather's name",
  "name.given.am": "የራስ ስም",
  "name.father.am": "የአባት ስም",
  "name.grandfather.am": "የአያት ስም",
  "name.hint": "Fill in both scripts when you can.",
  "name.no_last_name": "Ethiopian names have no last name.",
  "students.title": "Students",
  "students.intro": "Student records.",
  "students.number": "Student number",
  "students.status": "Status",
  "students.admission_date": "Admission date",
  "students.person": "Student",
  "students.enrollment": "Enrollment",
  "students.enrollment.year": "Academic year",
  "students.enrollment.level": "Grade level",
  "students.enrollment.section": "Section",
  "students.enrollment.roll_number": "Roll number",
  "students.status.active": "Active",
  "students.status.applicant": "Applicant",
  "students.search.label": "Search",
  "students.search.action": "Search",
  "students.search.placeholder": "Search by name or student number",
  "students.filter.all_statuses": "All statuses",
  "students.filter.all_years": "All years",
  "students.filter.all_levels": "All levels",
  "students.filter.all_sections": "All sections",
  "students.views.title": "Saved views",
  "students.views.none": "No saved view",
  "students.views.save": "Save current view",
  "students.views.delete": "Delete view",
  "students.views.name": "View name",
  "students.views.save_action": "Save",
  "students.loading": "Loading students…",
  "students.load_error": "Students could not be loaded",
  "students.empty": "No students yet",
  "students.empty_hint": "Register the first student to get started.",
  "students.open_profile": "Open profile",
  "students.not_enrolled": "Not enrolled",
  "students.not_set": "Not set",
  "students.count": "{{count}} students",
  "students.register.open": "Register student",
  "students.register.title": "Register a student",
  "students.register.hint": "Enter names in both scripts.",
  "students.register.saving": "Registering…",
  "students.register.anyway": "Register anyway",
  "students.register.submit": "Register student",
  "students.register.failed": "The student could not be registered.",
  "students.register.created": "{{name}} was registered.",
  "students.register.number_hint": "Leave blank to generate the next number.",
  "students.register.enrollment": "Enrollment",
  "students.register.no_enrollment": "No enrollment",
  "students.register.no_level": "No level",
  "students.register.no_section": "No section",
  "students.register.add_guardian": "Add a guardian",
  "students.sex": "Sex",
  "students.sex.unspecified": "Not specified",
  "students.sex.male": "Male",
  "students.sex.female": "Female",
  "students.date_of_birth": "Date of birth",
  "students.place_of_birth": "Place of birth",
  "students.nationality": "Nationality",
  "students.phone": "Phone",
  "students.email": "Email",
  "students.address": "Address",
  "students.notes": "Notes",
  "students.photo.title": "Photo",
  "students.photo.preview": "Student photo",
  "students.photo.choose": "Choose a photo",
  "students.photo.uploading": "Uploading photo…",
  "students.photo.failed": "The photo could not be uploaded.",
  "students.photo.replace": "Replace photo",
  "students.guardians": "Guardians",
  "students.guardian.relationship": "Relationship",
  "students.guardian.primary": "Primary contact",
  "students.guardian.can_pickup": "Can pick up the student",
  "students.guardian.add": "Link guardian",
  "students.guardian.remove": "Remove guardian",
  "students.guardian.empty": "No guardians linked yet",
  "students.guardian.failed": "The guardian change could not be saved.",
  "students.guardian.saving": "Saving…",
  "students.guardian.new_person": "New person",
  "students.guardian.existing_person": "Existing person",
  "students.guardian.search": "Search people",
  "students.guardian.search_placeholder": "Search by name",
  "students.guardian.choose_person": "Choose a person",
  "students.guardian.searching": "Searching…",
  "students.relationship.mother": "Mother",
  "students.relationship.father": "Father",
  "students.relationship.guardian": "Guardian",
  "students.relationship.grandparent": "Grandparent",
  "students.relationship.sibling": "Sibling",
  "students.relationship.other": "Other",
  "students.duplicate.title": "Possible duplicate",
  "students.duplicate.hint": "Check before saving.",
  "students.duplicate.similarity": "{{percent}}% similar",
  "students.tab.overview": "Overview",
  "students.enrollments": "Enrollments",
  "students.enrollments.empty": "No enrollments yet",
  "students.documents": "Documents",
  "students.documents.upload": "Upload document",
  "students.documents.empty": "No documents yet",
  "students.documents.delete": "Remove document",
  "students.documents.loading": "Loading documents…",
  "students.documents.load_error": "Documents could not be loaded",
  "students.documents.failed": "The document change could not be saved.",
  "students.documents.size": "{{kb}} KB",
  "students.profile_error": "The student could not be loaded",
  "students.back_to_list": "Back to students",
  "students.edit.open": "Edit",
  "students.edit.title": "Edit student record",
  "students.edit.saving": "Saving…",
  "students.edit.failed": "The changes could not be saved.",
  "students.medical": "Medical record",
  "students.exit_date": "Exit date",
  "students.exit_reason": "Exit reason",
  "academics.year.open": "Open",
  "files.uploading": "Uploading…",
};

const PERSON = {
  id: "person-1",
  given_name_en: "Abebe",
  father_name_en: "Kebede",
  grandfather_name_en: "Tessema",
  given_name_am: "አበበ",
  father_name_am: "ከበደ",
  grandfather_name_am: "ተሰማ",
  mother_name_en: null,
  mother_name_am: null,
  baptismal_name: null,
  nickname: null,
  sex: "male",
  date_of_birth: "2014-05-02",
  place_of_birth: null,
  nationality: null,
  phone: null,
  email: null,
  address: null,
  photo_file_id: null,
  custom: {},
  full_name: "Abebe Kebede Tessema",
  short_name: "Abebe Tessema",
  row_version: 1,
};

const STUDENT = {
  id: "student-1",
  student_number: "S-0001",
  status: "active" as const,
  admission_date: "2026-09-15",
  person: PERSON,
  enrollment: {
    id: "enr-1",
    student_id: "student-1",
    year_id: "year-1",
    year_code: "2026",
    year_name: "2026/27",
    level_id: "lvl-1",
    level_code: "grade-1",
    level_name: "Grade 1",
    section_id: "sec-1",
    section_code: "A",
    roll_number: "1",
    status: "active" as const,
    notes: null,
    row_version: 1,
  },
  row_version: 1,
};

const DETAIL = {
  ...STUDENT,
  exit_date: null,
  exit_reason: null,
  notes: "Allergy note",
  custom: {},
  enrollments: [STUDENT.enrollment],
  guardians: [
    {
      id: "guardian-1",
      student_id: "student-1",
      person_id: "person-2",
      relationship: "mother",
      is_primary: true,
      can_pickup: true,
      notes: null,
      person: {
        ...PERSON,
        id: "person-2",
        given_name_en: "Hanna",
        father_name_en: "Alemu",
        grandfather_name_en: "Desta",
        given_name_am: "ሃና",
        father_name_am: "አለሙ",
        grandfather_name_am: "ደስታ",
        full_name: "Hanna Alemu Desta",
      },
      row_version: 1,
    },
  ],
  medical: null,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function session() {
  return {
    id: "u-1",
    email: "registrar@demo.school",
    display_name: "Registrar",
    locale: "en",
    roles: ["registrar"],
    permissions: ["students.view", "students.manage", "academics.view", "people.view", "files.view"],
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [{ key: "students", label_key: "nav.students", path: "/students", module: "students" }],
    modules: ["students"],
    locale: "en",
    languages: ["en", "am"],
  };
}

function renderAt(path: string) {
  return render(
    <AppProviders
      initialMessages={messages}
      queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

let requests: MockRequest[] = [];

function stubRoutes(overrides?: (request: MockRequest) => Response | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const request: MockRequest = {
        url,
        method: (init?.method ?? "GET").toUpperCase(),
        body: typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null,
      };
      requests.push(request);
      if (url.endsWith("/api/v1/auth/me")) return json(session());
      if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
      if (url.endsWith("/api/v1/themes/active")) return json({}, 404);
      if (url.endsWith("/api/v1/themes/available")) return json({ items: [] });
      if (url.endsWith("/api/v1/academics/academic-years")) {
        return json({ items: [{ id: "year-1", code: "2026", name: "2026/27", status: "open" }], total: 1, current_year_id: "year-1" });
      }
      if (url.endsWith("/api/v1/academics/levels")) {
        return json({ items: [{ id: "lvl-1", code: "grade-1", name: "Grade 1", scope_level: 1, in_scope: true }], total: 1 });
      }
      if (url.includes("/api/v1/academics/sections")) return json({ items: [], total: 0 });
      const override = overrides?.(request);
      if (override) return override;
      if (request.method === "GET" && /\/api\/v1\/students(\?.*)?$/.test(url)) {
        return json({ items: [STUDENT], next_cursor: null, total: 1 });
      }
      if (request.method === "GET" && url.endsWith("/api/v1/students/student-1")) return json(DETAIL);
      if (request.method === "GET" && url.endsWith("/api/v1/students/student-1/documents")) {
        return json({ items: [] });
      }
      if (request.method === "POST" && url.endsWith("/api/v1/students/duplicate-check")) {
        return json({
          duplicate_warnings: [
            { person: PERSON, reason: "same_names_and_dob", similarity: 1 },
          ],
        });
      }
      if (request.method === "POST" && url.endsWith("/api/v1/students")) {
        return json({ ...DETAIL, duplicate_warnings: [] }, 201);
      }
      throw new Error(`Unexpected request: ${request.method} ${url}`);
    }),
  );
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
  localStorage.removeItem("erp.students.saved_views");
  requests = [];
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("students list", () => {
  it("lists students and applies search, status and saved views", async () => {
    stubRoutes();
    renderAt("/students");

    expect(await screen.findByTestId("student-row-student-1")).toBeInTheDocument();
    expect(screen.getByText("Abebe Kebede Tessema")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("student-search"), { target: { value: "Abebe" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() =>
      expect(requests.some((request) => request.url.includes("q=Abebe"))).toBe(true),
    );

    fireEvent.change(screen.getByTestId("student-status-filter"), { target: { value: "active" } });
    await waitFor(() =>
      expect(requests.some((request) => request.url.includes("status=active"))).toBe(true),
    );

    fireEvent.click(screen.getByRole("button", { name: "Save current view" }));
    fireEvent.change(screen.getByTestId("student-view-name"), { target: { value: "Active Abebe" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    const stored = JSON.parse(localStorage.getItem("erp.students.saved_views") ?? "[]");
    expect(stored[0].name).toBe("Active Abebe");
    expect(stored[0].filters.q).toBe("Abebe");
    expect(stored[0].filters.status).toBe("active");
  });

  it("shows the empty state when no student matches", async () => {
    stubRoutes((request) =>
      request.method === "GET" && /\/api\/v1\/students(\?.*)?$/.test(request.url)
        ? json({ items: [], next_cursor: null, total: 0 })
        : null,
    );
    renderAt("/students");
    expect(await screen.findByTestId("students-empty")).toBeInTheDocument();
  });
});

describe("student registration", () => {
  it("warns about duplicates before saving and then registers with both scripts", async () => {
    stubRoutes();
    renderAt("/students");

    fireEvent.click(await screen.findByTestId("student-register-open"));
    const dialog = await screen.findByRole("dialog");

    fireEvent.change(within(dialog).getByTestId("name-given_name_en"), { target: { value: "Abebe" } });
    fireEvent.change(within(dialog).getByTestId("name-father_name_en"), { target: { value: "Kebede" } });
    fireEvent.change(within(dialog).getByTestId("name-grandfather_name_en"), { target: { value: "Tessema" } });
    fireEvent.change(within(dialog).getByTestId("name-given_name_am"), { target: { value: "አበበ" } });
    fireEvent.change(within(dialog).getByLabelText("Date of birth"), { target: { value: "2014-05-02" } });

    fireEvent.click(within(dialog).getByRole("button", { name: "Register student" }));
    expect(await within(dialog).findByText(/Possible duplicate/)).toBeInTheDocument();
    expect(requests.some((request) => request.method === "POST" && request.url.endsWith("/api/v1/students"))).toBe(false);

    fireEvent.click(within(dialog).getByRole("button", { name: "Register anyway" }));
    await waitFor(() =>
      expect(requests.some((request) => request.method === "POST" && request.url.endsWith("/api/v1/students"))).toBe(true),
    );
    const create = requests.find(
      (request) => request.method === "POST" && request.url.endsWith("/api/v1/students"),
    );
    expect(create?.body).toMatchObject({
      person: {
        given_name_en: "Abebe",
        father_name_en: "Kebede",
        grandfather_name_en: "Tessema",
        given_name_am: "አበበ",
        date_of_birth: "2014-05-02",
      },
    });
    expect(await screen.findByTestId("student-registered")).toBeInTheDocument();
  });
});

describe("student profile", () => {
  it("shows the overview, guardians and document state", async () => {
    stubRoutes();
    renderAt("/students/student-1");

    expect(await screen.findByRole("heading", { name: "Abebe Kebede Tessema" })).toBeInTheDocument();
    expect(await screen.findByTestId("student-overview")).toBeInTheDocument();
    expect(screen.getByText("S-0001")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Guardians" }));
    expect(await screen.findByText("Hanna Alemu Desta")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Documents" }));
    expect(await screen.findByText("No documents yet")).toBeInTheDocument();
  });
});
