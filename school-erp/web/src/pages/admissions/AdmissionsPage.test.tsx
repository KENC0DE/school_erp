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
  "nav.admissions": "Admissions",
  "auth.logout": "Sign out",
  "common.loading": "Loading…",
  "common.cancel": "Cancel",
  "common.retry": "Retry",
  "common.request_id": "Request id",
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
  "admissions.title": "Admissions",
  "admissions.intro": "Take applications.",
  "admissions.search.label": "Search",
  "admissions.search.placeholder": "Search by name",
  "admissions.search.action": "Search",
  "admissions.status": "Status",
  "admissions.filter.all_statuses": "All statuses",
  "admissions.filter.all_years": "All years",
  "admissions.filter.all_levels": "All levels",
  "admissions.year": "Academic year",
  "admissions.level": "Grade level",
  "admissions.section": "Section",
  "admissions.section.auto": "Assigned automatically",
  "admissions.applied_on": "Applied on",
  "admissions.application_number": "Application number",
  "admissions.person": "Applicant",
  "admissions.source": "Source",
  "admissions.source.office": "Office",
  "admissions.source.phone": "Phone",
  "admissions.source.walk_in": "Walk-in",
  "admissions.source.public": "Public page",
  "admissions.not_set": "Not set",
  "admissions.count": "{{count}} applications",
  "admissions.loading": "Loading applications…",
  "admissions.load_error": "Applications could not be loaded",
  "admissions.empty": "No applications yet",
  "admissions.empty_hint": "Take the first application.",
  "admissions.new.title": "Take an application",
  "admissions.new.hint": "Enter the applicant's names.",
  "admissions.new.submit": "Save application",
  "admissions.new.saving": "Saving…",
  "admissions.new.failed": "The application could not be saved.",
  "admissions.new.anyway": "Save anyway",
  "admissions.duplicate.title": "Possible duplicate",
  "admissions.duplicate.hint": "Check before saving.",
  "admissions.duplicate.similarity": "{{percent}}% similar",
  "admissions.form.fields": "Custom fields",
  "admissions.form.hint": "Custom fields configured for admissions appear here.",
  "admissions.guardians": "Guardians",
  "admissions.guardian": "Guardian",
  "admissions.guardian.add": "Add guardian",
  "admissions.guardian.remove": "Remove",
  "admissions.guardian.empty": "No guardian yet",
  "admissions.guardian.relationship": "Relationship",
  "admissions.guardian.primary": "Primary contact",
  "admissions.guardian.can_pickup": "Can pick up the student",
  "admissions.guardian.wants_account": "Wants a parent account",
  "admissions.form.require_guardian": "At least one guardian is required.",
  "admissions.relationship.mother": "Mother",
  "admissions.relationship.father": "Father",
  "admissions.relationship.guardian": "Guardian",
  "admissions.relationship.grandparent": "Grandparent",
  "admissions.relationship.sibling": "Sibling",
  "admissions.relationship.other": "Other",
  "admissions.notes": "Notes",
  "admissions.back_to_list": "Back to admissions",
  "admissions.edit.open": "Edit",
  "admissions.decision.title": "Decision",
  "admissions.decision.hint": "Record the decision.",
  "admissions.decision.review": "Mark reviewed",
  "admissions.decision.test": "Send to test",
  "admissions.decision.offer": "Make an offer",
  "admissions.decision.accept": "Accept",
  "admissions.decision.reject": "Reject",
  "admissions.decision.withdraw": "Withdraw",
  "admissions.decision.saving": "Saving the decision…",
  "admissions.decision.failed": "The decision could not be saved.",
  "admissions.decision_notes": "Decision notes",
  "admissions.entrance_test": "Entrance test",
  "admissions.entrance_test.passed": "Passed",
  "admissions.entrance_test.failed": "Below the pass mark",
  "admissions.entrance_test.not_taken": "Not taken",
  "admissions.entrance_test.pending": "Waiting for a score",
  "admissions.entrance_test.disabled": "The entrance test is turned off.",
  "admissions.entrance_test.score": "Test score",
  "admissions.conversion.title": "Convert to student",
  "admissions.conversion.hint": "Conversion creates the student record.",
  "admissions.conversion.action": "Convert to student",
  "admissions.conversion.saving": "Converting…",
  "admissions.conversion.failed": "The application could not be converted.",
  "admissions.conversion.done": "{{name}} is now a student.",
  "admissions.conversion.create_accounts": "Create parent accounts",
  "admissions.conversion.accounts": "Parent accounts",
  "admissions.conversion.accounts.hint": "Guardians get an invitation.",
  "admissions.conversion.account.create": "Create",
  "admissions.conversion.account.existing_user": "Already has an account",
  "admissions.conversion.account.no_email": "No email address",
  "admissions.conversion.account.role_missing": "Parent role is missing",
  "admissions.conversion.not_ready": "Accept the application before converting it.",
  "admissions.student": "Student",
  "admissions.student_number": "Student number",
  "admissions.documents": "Documents",
  "admissions.documents.upload": "Upload document",
  "admissions.documents.empty": "No documents yet",
  "admissions.documents.delete": "Remove document",
  "admissions.documents.loading": "Loading documents…",
  "admissions.documents.load_error": "Documents could not be loaded",
  "admissions.documents.failed": "The document change could not be saved.",
  "admissions.documents.size": "{{kb}} KB",
  "admissions.status.applied": "Applied",
  "admissions.status.reviewed": "Reviewed",
  "admissions.status.test": "Entrance test",
  "admissions.status.offered": "Offered",
  "admissions.status.accepted": "Accepted",
  "admissions.status.enrolled": "Enrolled",
  "admissions.status.rejected": "Rejected",
  "admissions.status.withdrawn": "Withdrawn",
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
  "custom.loading": "Loading fields…",
  "custom.empty": "No custom fields",
  "custom.optional": "optional",
  "custom.choose": "Choose",
  "custom.multiselect.hint": "Choose one or more",
  "common.error": "Something went wrong",
  "admissions.public.hint": "Fill in the applicant's details.",
  "admissions.public.closed": "Applications are closed right now",
  "admissions.public.closed_hint": "Please contact the school office to apply.",
  "admissions.public.unavailable": "The application page is unavailable",
  "admissions.public.success_heading": "Application received",
  "admissions.public.success": "The application number is {{number}}.",
  "admissions.public.success_hint": "Keep this number. The school will contact you about {{name}}.",
  "admissions.public.another": "Submit another application",
  "admissions.public.submit": "Submit application",
  "admissions.public.saving": "Submitting…",
  "admissions.public.failed": "The application could not be submitted.",
  "admissions.public.choose_level": "Choose a grade level",
  "admissions.public.wait": "You can submit in {{seconds}} seconds.",
  "admissions.public.website": "Leave this field empty",
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

const SUMMARY = {
  id: "app-1",
  application_number: "ADM-2026-0001",
  status: "offered" as const,
  applied_on: "2026-05-01",
  source: "office",
  person: PERSON,
  year_id: "year-1",
  year_code: "2026",
  year_name: "2026/27",
  level_id: "lvl-1",
  level_code: "grade-1",
  level_name: "Grade 1",
  section_id: null,
  section_code: null,
  entrance_test_score: 80,
  student_id: null,
  student_number: null,
  row_version: 1,
};

const DETAIL = {
  ...SUMMARY,
  notes: "Walk-in application",
  custom: {},
  guardians: [
    {
      id: "guardian-1",
      application_id: "app-1",
      person_id: "person-2",
      relationship: "mother",
      is_primary: true,
      can_pickup: true,
      wants_account: true,
      account_user_id: null,
      notes: null,
      person: { ...PERSON, id: "person-2", full_name: "Hanna Alemu Desta" },
      row_version: 1,
    },
  ],
  decision_notes: null,
  decided_by: null,
  decided_at: null,
  converted_at: null,
  test_max_score: 100,
  test_pass_score: 50,
  test_passed: true,
};

const FORM = {
  entity_type: "admission_application",
  fields: [],
  entrance_test_enabled: true,
  entrance_test_max_score: 100,
  entrance_test_pass_score: 50,
  require_guardian: true,
  public_form_enabled: false,
};

const CONVERSION = {
  can_convert: true,
  reason: null,
  student_number: "S-0001",
  student_number_generated: true,
  year_code: "2026",
  level_code: "grade-1",
  section_code: "A",
  section_source: "auto",
  guardian_count: 1,
  accounts: [
    { person_id: "person-2", name: "Hanna Alemu Desta", email: "hanna@example.com", action: "create" },
  ],
  warnings: [],
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
    permissions: ["admissions.view", "admissions.manage", "admissions.decide", "academics.view"],
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [{ key: "admissions", label_key: "nav.admissions", path: "/admissions", module: "admissions" }],
    modules: ["admissions"],
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
        return json({
          items: [{ id: "year-1", code: "2026", name: "2026/27", status: "open" }],
          total: 1,
          current_year_id: "year-1",
        });
      }
      if (url.endsWith("/api/v1/academics/levels")) {
        return json({
          items: [{ id: "lvl-1", code: "grade-1", name: "Grade 1", scope_level: 1, in_scope: true }],
          total: 1,
        });
      }
      if (url.includes("/api/v1/academics/sections")) {
        return json({
          items: [
            {
              id: "sec-1",
              year_id: "year-1",
              level_id: "lvl-1",
              code: "A",
              name: "A",
              is_active: true,
            },
          ],
          total: 1,
        });
      }
      const override = overrides?.(request);
      if (override) return override;
      if (url.endsWith("/api/v1/admissions/form")) return json(FORM);
      if (url.endsWith("/api/v1/admissions/app-1/conversion")) return json(CONVERSION);
      if (url.endsWith("/api/v1/admissions/app-1/documents")) return json({ items: [] });
      if (url.endsWith("/api/v1/admissions/app-1")) return json(DETAIL);
      if (request.method === "POST" && url.endsWith("/api/v1/admissions/preview")) {
        return json({
          will_create: "admission_application",
          application_number: "ADM-2026-0001",
          full_name: "Abebe Kebede Tessema",
          year_code: "2026",
          level_code: "grade-1",
          section_code: null,
          guardian_count: 1,
          custom_field_count: 0,
          duplicate_warnings: [],
        });
      }
      if (request.method === "POST" && url.endsWith("/api/v1/admissions")) {
        return json({ ...DETAIL, duplicate_warnings: [] }, 201);
      }
      if (request.method === "GET" && /\/api\/v1\/admissions(\?.*)?$/.test(url)) {
        return json({ items: [SUMMARY], next_cursor: null, total: 1 });
      }
      throw new Error(`Unexpected request: ${request.method} ${url}`);
    }),
  );
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
  requests = [];
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("admissions list", () => {
  it("lists applications and applies search and filters", async () => {
    stubRoutes();
    renderAt("/admissions");

    expect(await screen.findByTestId("admission-row-app-1")).toBeInTheDocument();
    expect(screen.getByText("ADM-2026-0001")).toBeInTheDocument();
    expect(screen.getByText("Abebe Kebede Tessema")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("admission-search"), { target: { value: "Abebe" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() =>
      expect(requests.some((request) => request.url.includes("q=Abebe"))).toBe(true),
    );

    fireEvent.change(screen.getByTestId("admission-status-filter"), {
      target: { value: "offered" },
    });
    await waitFor(() =>
      expect(requests.some((request) => request.url.includes("status=offered"))).toBe(true),
    );
  });

  it("shows the empty state when no application matches", async () => {
    stubRoutes((request) =>
      request.method === "GET" && /\/api\/v1\/admissions(\?.*)?$/.test(request.url)
        ? json({ items: [], next_cursor: null, total: 0 })
        : null,
    );
    renderAt("/admissions");
    expect(await screen.findByTestId("admissions-empty")).toBeInTheDocument();
  });
});

describe("taking an application", () => {
  it("warns about a duplicate and creates the application when confirmed", async () => {
    stubRoutes((request) =>
      request.method === "POST" && request.url.endsWith("/api/v1/admissions/preview")
        ? json({
            will_create: "admission_application",
            application_number: "ADM-2026-0001",
            full_name: "Abebe Kebede Tessema",
            year_code: "2026",
            level_code: "grade-1",
            section_code: null,
            guardian_count: 1,
            custom_field_count: 0,
            duplicate_warnings: [{ person: PERSON, reason: "same_names_and_dob", similarity: 1 }],
          })
        : null,
    );
    renderAt("/admissions/new");

    fireEvent.change(await screen.findByTestId("name-given_name_en"), {
      target: { value: "Abebe" },
    });
    fireEvent.change(screen.getByTestId("name-father_name_en"), { target: { value: "Kebede" } });
    fireEvent.change(screen.getByTestId("name-grandfather_name_en"), {
      target: { value: "Tessema" },
    });
    fireEvent.change(screen.getByTestId("admission-level"), { target: { value: "lvl-1" } });
    fireEvent.change(screen.getByTestId("admission-score"), { target: { value: "80" } });

    fireEvent.click(screen.getByText("Add guardian"));
    const guardianFieldset = screen.getByTestId("admission-guardians");
    fireEvent.change(within(guardianFieldset).getByTestId("name-given_name_en"), {
      target: { value: "Hanna" },
    });
    fireEvent.change(within(guardianFieldset).getByTestId("name-father_name_en"), {
      target: { value: "Alemu" },
    });
    fireEvent.change(within(guardianFieldset).getByTestId("name-grandfather_name_en"), {
      target: { value: "Desta" },
    });

    fireEvent.click(screen.getByTestId("admission-submit"));
    expect(await screen.findByText(/Possible duplicate/)).toBeInTheDocument();
    expect(
      requests.some(
        (request) => request.method === "POST" && request.url.endsWith("/api/v1/admissions"),
      ),
    ).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Save anyway" }));
    await waitFor(() =>
      expect(
        requests.some(
          (request) => request.method === "POST" && request.url.endsWith("/api/v1/admissions"),
        ),
      ).toBe(true),
    );
    const create = requests.find(
      (request) => request.method === "POST" && request.url.endsWith("/api/v1/admissions"),
    );
    expect(create?.body).toMatchObject({
      source: "office",
      year_id: "year-1",
      level_id: "lvl-1",
      entrance_test_score: 80,
      person: {
        given_name_en: "Abebe",
        father_name_en: "Kebede",
        grandfather_name_en: "Tessema",
      },
      guardians: [
        {
          relationship: "mother",
          is_primary: true,
          person: { given_name_en: "Hanna", father_name_en: "Alemu", grandfather_name_en: "Desta" },
        },
      ],
    });
  });
});

describe("public application", () => {
  const PUBLIC_FORM = {
    enabled: true,
    school_name: "Demo School",
    form_token: "signed-form-token",
    min_seconds: 0,
    fields: [],
    years: [{ id: "year-1", code: "2026", name: "2026/27" }],
    levels: [{ id: "lvl-1", code: "grade-1", name: "Grade 1" }],
    entrance_test_enabled: true,
    entrance_test_max_score: 100,
    entrance_test_pass_score: 50,
    require_guardian: true,
  };

  it("shows the closed message when the school has not opened the page", async () => {
    localStorage.removeItem("erp.access_token");
    stubRoutes((request) =>
      request.url.endsWith("/api/v1/admissions/public/form")
        ? json({ ...PUBLIC_FORM, enabled: false, form_token: null })
        : null,
    );
    renderAt("/apply");
    expect(await screen.findByTestId("public-apply-closed")).toBeInTheDocument();
  });

  it("submits a public application with the form token and an empty honeypot", async () => {
    localStorage.removeItem("erp.access_token");
    stubRoutes((request) => {
      if (request.url.endsWith("/api/v1/admissions/public/form")) return json(PUBLIC_FORM);
      if (request.method === "POST" && request.url.endsWith("/api/v1/admissions/public/applications")) {
        return json(
          {
            application_number: "ADM-2026-0007",
            full_name: "Abebe Kebede Tessema",
            status: "applied",
            year_code: "2026",
            level_code: "grade-1",
          },
          201,
        );
      }
      return null;
    });
    renderAt("/apply");

    const applicantName = within((await screen.findAllByTestId("name-fields"))[0]);
    fireEvent.change(applicantName.getByTestId("name-given_name_en"), {
      target: { value: "Abebe" },
    });
    fireEvent.change(applicantName.getByTestId("name-father_name_en"), { target: { value: "Kebede" } });
    fireEvent.change(applicantName.getByTestId("name-grandfather_name_en"), {
      target: { value: "Tessema" },
    });
    fireEvent.change(screen.getByTestId("public-apply-level"), { target: { value: "lvl-1" } });

    fireEvent.click(screen.getByText("Add guardian"));
    const guardianFieldset = screen.getByTestId("admission-guardians");
    fireEvent.change(within(guardianFieldset).getAllByTestId("name-given_name_en")[0], {
      target: { value: "Hanna" },
    });

    fireEvent.click(screen.getByTestId("public-apply-submit"));
    expect(await screen.findByTestId("public-apply-done")).toBeInTheDocument();

    const submitted = requests.find(
      (request) => request.method === "POST" && request.url.endsWith("/api/v1/admissions/public/applications"),
    );
    expect(submitted?.body).toMatchObject({
      form_token: "signed-form-token",
      website: "",
      year_id: "year-1",
      level_id: "lvl-1",
      person: { given_name_en: "Abebe", father_name_en: "Kebede" },
    });
    expect(screen.getByText(/ADM-2026-0007/)).toBeInTheDocument();
  });
});

describe("application profile", () => {
  it("records a decision and converts an accepted application", async () => {
    let accepted = false;
    stubRoutes((request) => {
      if (request.method === "GET" && request.url.endsWith("/api/v1/admissions/app-1")) {
        return json(accepted ? { ...DETAIL, status: "accepted", row_version: 2 } : DETAIL);
      }
      if (request.method === "POST" && request.url.endsWith("/api/v1/admissions/app-1/decision")) {
        accepted = true;
        return json({
          application: { ...DETAIL, status: "accepted", row_version: 2 },
          previous_status: "offered",
          status: "accepted",
        });
      }
      if (request.method === "POST" && request.url.endsWith("/api/v1/admissions/app-1/convert")) {
        return json({
          application: {
            ...DETAIL,
            status: "enrolled",
            student_id: "student-1",
            student_number: "S-0001",
            row_version: 3,
          },
          student_id: "student-1",
          student_number: "S-0001",
          enrollment_id: "enr-1",
          guardian_ids: ["guardian-1"],
          accounts: CONVERSION.accounts,
          warnings: [],
        });
      }
      return null;
    });
    renderAt("/admissions/app-1");

    expect(await screen.findByText("ADM-2026-0001 · Abebe Kebede Tessema")).toBeInTheDocument();
    expect(screen.getByTestId("admission-test-state")).toBeInTheDocument();
    expect(screen.getByTestId("admission-guardian-guardian-1")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("admission-decide-accepted"));
    await waitFor(() =>
      expect(
        requests.some((request) => request.url.endsWith("/api/v1/admissions/app-1/decision")),
      ).toBe(true),
    );
    const decision = requests.find((request) =>
      request.url.endsWith("/api/v1/admissions/app-1/decision"),
    );
    expect(decision?.body).toMatchObject({ status: "accepted", row_version: 1 });

    expect(await screen.findByTestId("admission-conversion-preview")).toBeInTheDocument();
    expect(screen.getByText("S-0001")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("admission-convert"));
    await waitFor(() =>
      expect(
        requests.some((request) => request.url.endsWith("/api/v1/admissions/app-1/convert")),
      ).toBe(true),
    );
    expect(await screen.findByTestId("admission-converted")).toBeInTheDocument();
  });
});
