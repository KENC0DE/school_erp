import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  "common.retry": "Retry",
  "common.request_id": "Request id",
  "common.close": "Close",
  "students.title": "Students",
  "students.back_to_list": "Back to students",
  "students.status": "Status",
  "students.status.active": "Active",
  "students.status.promoted": "Promoted",
  "students.status.repeating": "Repeating",
  "students.loading": "Loading students…",
  "students.load_error": "Students could not be loaded",
  "students.empty": "No students yet",
  "students.register.open": "Register student",
  "students.progress.open": "Promote and transfer",
  "students.progress.title": "Promotion and transfer",
  "students.progress.intro": "Preview a year-end promotion.",
  "students.progress.permission_denied":
    "You do not have permission to manage promotions.",
  "students.progress.select_years":
    "Choose a source year that starts before the target year.",
  "students.progress.source_year": "From academic year",
  "students.progress.target_year": "To academic year",
  "students.progress.level": "Grade level",
  "students.progress.section": "Section",
  "students.progress.all_levels": "All levels",
  "students.progress.all_sections": "All sections",
  "students.progress.reason": "Reason or note",
  "students.progress.reason_hint": "Stored in the activity history.",
  "students.progress.preview": "Preview promotion",
  "students.progress.previewing": "Preparing the preview…",
  "students.progress.apply": "Apply promotion",
  "students.progress.applying": "Applying…",
  "students.progress.applied":
    "Promotion applied: {{promoted}} promoted, {{repeated}} repeating, {{graduated}} graduated and {{skipped}} skipped.",
  "students.progress.summary":
    "{{total}} students · {{promote}} promoted · {{repeat}} repeat · {{graduate}} graduated · {{skip}} skipped",
  "students.progress.blocking_count":
    "{{count}} row(s) need attention before applying",
  "students.progress.loading": "Loading the promotion preview…",
  "students.progress.load_error": "The promotion preview could not be prepared",
  "students.progress.apply_error": "The promotion batch could not be applied.",
  "students.progress.empty": "No students to promote",
  "students.progress.empty_hint":
    "Choose two academic years and preview to see the eligible students.",
  "students.progress.column.student": "Student",
  "students.progress.column.current": "Current placement",
  "students.progress.column.action": "Action",
  "students.progress.column.target": "Target placement",
  "students.progress.column.warnings": "Warnings",
  "students.progress.action.promote": "Promote",
  "students.progress.action.repeat": "Repeat",
  "students.progress.action.graduate": "Graduate",
  "students.progress.action.skip": "Skip",
  "students.progress.none": "None",
  "students.progress.auto_section": "Automatic",
  "students.progress.warning.graduate_not_final":
    "Only students in the final grade level can graduate.",
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
    permissions: ["students.view", "students.manage", "academics.view"],
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [
      {
        key: "students",
        label_key: "nav.students",
        path: "/students",
        module: "students",
      },
    ],
    modules: ["students"],
    locale: "en",
    languages: ["en", "am"],
  };
}

function renderAt(path: string) {
  return render(
    <AppProviders
      initialMessages={messages}
      queryClient={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

function row(overrides: Record<string, unknown> = {}) {
  return {
    student_id: "student-1",
    student_number: "S-0001",
    full_name: "Abebe Kebede Tessema",
    status: "active",
    current_level_id: "lvl-5",
    current_level_name: "Grade 5",
    current_level_sort_order: 5,
    current_section_id: "sec-a",
    current_section_code: "A",
    action: "promote",
    next_level_id: "lvl-6",
    next_level_name: "Grade 6",
    target_level_id: "lvl-6",
    target_level_name: "Grade 6",
    target_section_id: "sec-target-a",
    target_section_code: "A",
    warnings: [],
    blocking: false,
    ...overrides,
  };
}

function previewBody(rows: Record<string, unknown>[]) {
  const count = (action: string) =>
    rows.filter((item) => item.action === action).length;
  return {
    source_year_id: "year-1",
    target_year_id: "year-2",
    total: rows.length,
    promote: count("promote"),
    repeat: count("repeat"),
    graduate: count("graduate"),
    skip: count("skip"),
    blocking: rows.filter((item) => item.blocking).length,
    items: rows,
  };
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
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      };
      requests.push(request);
      if (url.endsWith("/api/v1/auth/me")) return json(session());
      if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
      if (url.endsWith("/api/v1/themes/active")) return json({}, 404);
      if (url.endsWith("/api/v1/themes/available")) return json({ items: [] });
      if (url.endsWith("/api/v1/academics/academic-years")) {
        return json({
          items: [
            { id: "year-2", code: "2027", name: "2027/28", status: "planned" },
            { id: "year-1", code: "2026", name: "2026/27", status: "open" },
          ],
          total: 2,
          current_year_id: "year-1",
        });
      }
      if (url.endsWith("/api/v1/academics/levels")) {
        return json({
          items: [
            {
              id: "lvl-5",
              code: "g5",
              name: "Grade 5",
              scope_level: 5,
              in_scope: true,
            },
            {
              id: "lvl-6",
              code: "g6",
              name: "Grade 6",
              scope_level: 6,
              in_scope: true,
            },
          ],
          total: 2,
        });
      }
      if (url.includes("/api/v1/academics/sections")) {
        return json({
          items: [
            {
              id: "sec-a",
              year_id: "year-1",
              level_id: "lvl-5",
              code: "A",
              name: null,
              is_active: true,
            },
          ],
          total: 1,
        });
      }
      if (
        request.method === "POST" &&
        url.endsWith("/api/v1/students/promotions/apply")
      ) {
        return json({
          source_year_id: "year-1",
          target_year_id: "year-2",
          enrolled: 1,
          promoted: 1,
          repeated: 1,
          graduated: 0,
          skipped: 0,
          items: [],
        });
      }
      const override = overrides?.(request);
      if (override) return override;
      if (
        request.method === "POST" &&
        url.endsWith("/api/v1/students/promotions/preview")
      ) {
        const exceptions =
          (request.body?.exceptions as {
            student_id: string;
            action: string;
          }[]) ?? [];
        const repeated = exceptions.find((item) => item.action === "repeat");
        const rows = [row()];
        if (repeated?.student_id === "student-2") {
          rows.push(
            row({
              student_id: "student-2",
              student_number: "S-0002",
              full_name: "Marta Alemu Desta",
              action: "repeat",
              target_level_id: "lvl-5",
              target_level_name: "Grade 5",
            }),
          );
        } else {
          rows.push(
            row({
              student_id: "student-2",
              student_number: "S-0002",
              full_name: "Marta Alemu Desta",
            }),
          );
        }
        return json(previewBody(rows));
      }
      throw new Error(`Unexpected request: ${request.method} ${url}`);
    }),
  );
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
  requests = [];
});

async function openPreview() {
  await waitFor(() =>
    expect(screen.getByTestId("promotion-source-year")).toHaveValue("year-1"),
  );
  fireEvent.click(screen.getByTestId("promotion-preview"));
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("promotion page", () => {
  it("previews a section, records an exception and applies the batch", async () => {
    stubRoutes();
    renderAt("/students/promotions");

    expect(
      await screen.findByRole("heading", { name: "Promotion and transfer" }),
    ).toBeInTheDocument();
    await openPreview();

    expect(await screen.findByTestId("promotion-table")).toBeInTheDocument();
    expect(screen.getByTestId("promotion-summary")).toHaveTextContent(
      "2 students",
    );
    expect(screen.getByTestId("promotion-row-student-1")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("promotion-action-student-2"), {
      target: { value: "repeat" },
    });
    await waitFor(() => {
      const preview = requests
        .filter((item) => item.url.endsWith("/promotions/preview"))
        .at(-1);
      expect(preview?.body?.exceptions).toEqual([
        { student_id: "student-2", action: "repeat" },
      ]);
    });
    expect(screen.getByTestId("promotion-summary")).toHaveTextContent(
      "1 repeat",
    );

    fireEvent.change(screen.getByTestId("promotion-reason"), {
      target: { value: "End of year 2026/27" },
    });
    fireEvent.click(screen.getByTestId("promotion-apply"));

    expect(await screen.findByTestId("promotion-applied")).toHaveTextContent(
      "1 promoted",
    );
    const applied = requests.find((item) =>
      item.url.endsWith("/promotions/apply"),
    );
    expect(applied?.body).toMatchObject({
      source_year_id: "year-1",
      target_year_id: "year-2",
      reason: "End of year 2026/27",
      exceptions: [{ student_id: "student-2", action: "repeat" }],
    });
  });

  it("shows the empty state when nothing is eligible", async () => {
    stubRoutes((request) =>
      request.method === "POST" && request.url.endsWith("/promotions/preview")
        ? json(previewBody([]))
        : null,
    );
    renderAt("/students/promotions");

    await openPreview();
    expect(
      await screen.findByTestId("promotion-preview-empty"),
    ).toBeInTheDocument();
  });

  it("disables apply while a row is blocking", async () => {
    stubRoutes((request) =>
      request.method === "POST" && request.url.endsWith("/promotions/preview")
        ? json(
            previewBody([
              row({
                action: "graduate",
                target_level_id: "lvl-5",
                target_level_name: "Grade 5",
                warnings: ["students.progress.warning.graduate_not_final"],
                blocking: true,
              }),
            ]),
          )
        : null,
    );
    renderAt("/students/promotions");

    await openPreview();
    expect(await screen.findByTestId("promotion-table")).toBeInTheDocument();
    expect(screen.getByTestId("promotion-apply")).toBeDisabled();
    expect(
      screen.getByText("Only students in the final grade level can graduate."),
    ).toBeInTheDocument();
  });
});
