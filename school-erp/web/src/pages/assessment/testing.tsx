import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import coreEn from "../../../../backend/core/i18n/en.json";
import assessmentEn from "../../../../backend/modules/assessment/i18n/en.json";
import { AppProviders, AppRoutes } from "../../App";
import type { Structure } from "./types";

export const assessmentMessages: Record<string, string> = {
  ...coreEn,
  ...Object.fromEntries(
    Object.entries(assessmentEn).map(([key, value]) => [`assessment.${key}`, value]),
  ),
};

export interface MockRequest {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function session(permissions: string[]) {
  return {
    id: "u-1",
    email: "academichead@demo.school",
    display_name: "Academic Head",
    locale: "en",
    roles: ["academic_head"],
    permissions,
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [
      {
        key: "assessment",
        label_key: "assessment.nav",
        path: "/assessment",
        module: "assessment",
      },
    ],
    modules: ["assessment"],
    locale: "en",
    languages: ["en", "am"],
  };
}

export function stubAssessment(
  permissions: string[],
  handler: (request: MockRequest) => Response,
): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) return json(session(permissions));
      if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
      return handler({
        url,
        method: (init?.method ?? "GET").toUpperCase(),
        body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
      });
    }),
  );
}

export function renderAssessment() {
  return render(
    <AppProviders
      initialMessages={assessmentMessages}
      queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={["/assessment"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

export const TERM = {
  id: "term-1",
  year_id: "year-1",
  number: 1,
  name: "Semester 1",
  name_am: "ሴሚስተር 1",
  start_date: "2026-09-01",
  end_date: "2027-01-15",
  start_date_display: "Meskerem 1, 2019 EC",
  end_date_display: "Tir 7, 2019 EC",
  status: "open",
  row_version: 1,
};

export const YEAR = {
  id: "year-1",
  code: "2026",
  name: "2026/27",
  name_am: null,
  start_date: "2026-09-01",
  end_date: "2027-06-30",
  start_date_display: "Meskerem 1, 2019 EC",
  end_date_display: "Sene 30, 2019 EC",
  term_system: "semester",
  status: "open",
  current_term_id: "term-1",
  curriculum_profile_id: null,
  curriculum_profile_code: null,
  terms: [TERM],
  row_version: 1,
};

export const YEARS = { items: [YEAR], total: 1, current_year_id: "year-1" };

export const LEVELS = {
  items: [
    {
      id: "lvl-1",
      code: "g5",
      name: "Grade 5",
      name_am: null,
      scope_level: 5,
      sort_order: 6,
      is_active: true,
      is_starter: false,
      is_verified: true,
      in_scope: true,
      row_version: 1,
    },
  ],
  total: 1,
  scope: {
    first_level: 0,
    last_level: 8,
    level_count: 9,
    stage_count: 2,
    scope_levels: [0, 1, 2, 3, 4, 5, 6, 7, 8],
  },
};

export const STAGES = {
  items: [
    {
      id: "stage-1",
      code: "primary",
      name: "Primary",
      name_am: null,
      sort_order: 1,
      is_active: true,
      row_version: 1,
    },
  ],
  total: 1,
};

export const SUBJECTS = {
  items: [
    {
      id: "sub-1",
      code: "mathematics",
      name: "Mathematics",
      name_am: null,
      sort_order: 1,
      is_active: true,
      row_version: 1,
    },
  ],
  total: 1,
};

export const COMPONENTS = [
  {
    id: "component-1",
    key: "quizzes",
    name: "Quizzes",
    name_am: null,
    max_points: "10",
    aggregation: "average" as const,
    absent_counts_as_zero: false,
    best_n: null,
    cap: null,
    sort_order: 0,
    is_active: true,
    row_version: 1,
  },
  {
    id: "component-2",
    key: "final",
    name: "Final exam",
    name_am: null,
    max_points: "90",
    aggregation: "average" as const,
    absent_counts_as_zero: false,
    best_n: null,
    cap: null,
    sort_order: 1,
    is_active: true,
    row_version: 1,
  },
];

export function structure(overrides: Partial<Structure> = {}): Structure {
  return {
    id: "structure-1",
    year_id: "year-1",
    year_code: "2026",
    scope_type: "school",
    scope_key: "school",
    level_id: null,
    level_name: null,
    stage_id: null,
    stage_name: null,
    subject_id: null,
    subject_name: null,
    name: "School mark structure",
    name_am: null,
    term_system: "semester",
    year_mode: "average",
    year_weights: null,
    precision: 2,
    rounding: "half_up",
    intended_total: "100",
    total: "100",
    total_matches: true,
    descriptive_mode: false,
    version: 2,
    is_active: true,
    row_version: 3,
    components: COMPONENTS,
    ...overrides,
  };
}

/** The endpoints every assessment screen reads before its own handler runs. */
export function baseRoutes(request: MockRequest): Response {
  const { url } = request;
  if (url.includes("/api/v1/assessment/structures")) return json({ items: [], next_cursor: null, total: 0 });
  if (url.includes("/api/v1/academics/academic-years")) return json(YEARS);
  if (url.includes("/api/v1/academics/levels")) return json(LEVELS);
  if (url.includes("/api/v1/academics/stages")) return json(STAGES);
  if (url.includes("/api/v1/academics/subjects")) return json(SUBJECTS);
  throw new Error(`Unexpected request: ${request.method} ${url}`);
}
