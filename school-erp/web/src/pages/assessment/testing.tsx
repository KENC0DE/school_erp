import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import coreEn from "../../../../backend/core/i18n/en.json";
import assessmentEn from "../../../../backend/modules/assessment/i18n/en.json";
import { AppProviders, AppRoutes } from "../../App";
import type {
  AssessmentListItem,
  DashboardAnomaly,
  DashboardOut,
  DashboardRow,
  GradeScale,
  MarkingWindow,
  ScaleAssignment,
  ScoreSheet,
  Structure,
  Submission,
} from "./types";

export const assessmentMessages: Record<string, string> = {
  ...coreEn,
  ...Object.fromEntries(
    Object.entries(assessmentEn).map(([key, value]) => [
      `assessment.${key}`,
      value,
    ]),
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
        body: init?.body
          ? (JSON.parse(String(init.body)) as Record<string, unknown>)
          : null,
      });
    }),
  );
}

export function renderAssessment() {
  return render(
    <AppProviders
      initialMessages={assessmentMessages}
      queryClient={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
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

export const SECTIONS = {
  items: [
    {
      id: "sec-1",
      year_id: "year-1",
      year_code: "2026",
      level_id: "lvl-1",
      level_code: "g5",
      level_name: "Grade 5",
      code: "G5A",
      name: null,
      name_am: null,
      capacity: 40,
      homeroom_user_id: null,
      homeroom_name: null,
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
  if (url.includes("/api/v1/assessment/structures"))
    return json({ items: [], next_cursor: null, total: 0 });
  if (url.includes("/api/v1/academics/academic-years")) return json(YEARS);
  if (url.includes("/api/v1/academics/levels")) return json(LEVELS);
  if (url.includes("/api/v1/academics/stages")) return json(STAGES);
  if (url.includes("/api/v1/academics/subjects")) return json(SUBJECTS);
  if (url.includes("/api/v1/academics/sections")) return json(SECTIONS);
  throw new Error(`Unexpected request: ${request.method} ${url}`);
}

export const SCALE_BANDS = [
  {
    id: "band-1",
    min_value: "0",
    max_value: "50",
    label: "F",
    remark: null,
    gpa_points: "0",
    is_pass: false,
    color: null,
    sort_order: 0,
    row_version: 1,
  },
  {
    id: "band-2",
    min_value: "50",
    max_value: "75",
    label: "C",
    remark: null,
    gpa_points: "2",
    is_pass: true,
    color: null,
    sort_order: 1,
    row_version: 1,
  },
  {
    id: "band-3",
    min_value: "75",
    max_value: "85",
    label: "C+",
    remark: null,
    gpa_points: "3",
    is_pass: true,
    color: null,
    sort_order: 2,
    row_version: 1,
  },
  {
    id: "band-4",
    min_value: "85",
    max_value: "100",
    label: "A",
    remark: null,
    gpa_points: "4",
    is_pass: true,
    color: null,
    sort_order: 3,
    row_version: 1,
  },
];

export function gradeScale(overrides: Partial<GradeScale> = {}): GradeScale {
  return {
    id: "scale-1",
    name: "School grading scale",
    name_am: null,
    type: "numeric_bands",
    description: null,
    is_default: true,
    lower_bound: "0",
    upper_bound: "100",
    precision: 2,
    rounding: "half_up",
    version: 1,
    effective_from: null,
    effective_to: null,
    is_active: true,
    notes: null,
    row_version: 1,
    bands: SCALE_BANDS,
    assignment_count: 0,
    ...overrides,
  };
}

export function scaleAssignment(
  overrides: Partial<ScaleAssignment> = {},
): ScaleAssignment {
  return {
    id: "assignment-1",
    scale_id: "scale-1",
    scale_name: "School grading scale",
    context: "level",
    scope_key: "level:lvl-1",
    assessment_id: null,
    assessment_title: null,
    subject_id: null,
    subject_name: null,
    level_id: "lvl-1",
    level_name: "Grade 5",
    stage_id: null,
    stage_name: null,
    notes: null,
    row_version: 1,
    ...overrides,
  };
}

export const ASSESSMENTS = {
  items: [
    {
      id: "exam-1",
      title: "Mathematics mid-term",
      year_id: "year-1",
      term_name: "Semester 1",
      section_code: "G5A",
      subject_name: "Mathematics",
      component_name: "Final exam",
    },
  ],
  next_cursor: null,
  total: 1,
};

/** Grade routes shared by the grade panel tests. */
export function gradeRoutes(
  request: MockRequest,
  scales: GradeScale[] = [gradeScale()],
  assignments: ScaleAssignment[] = [],
): Response {
  const { url, method } = request;
  if (url.includes("/api/v1/assessment/scale-assignments")) {
    if (method === "POST") return json(scaleAssignment(), 201);
    return json({ items: assignments, total: assignments.length });
  }
  if (url.match(/\/api\/v1\/assessment\/scales\/[^/]+\/test$/)) {
    return json({
      value: "75",
      label: "C+",
      remark: null,
      gpa_points: "3",
      is_pass: true,
      color: null,
      band_min: "75",
      band_max: "85",
      scale_name: "School grading scale",
      scale_version: 1,
    });
  }
  if (url.includes("/api/v1/assessment/scales")) {
    if (method === "POST" || method === "PATCH") return json(scales[0], 201);
    if (method === "DELETE") return json({ id: "scale-1", deleted: true });
    return json({ items: scales, total: scales.length });
  }
  if (url.includes("/api/v1/assessment/assessments")) return json(ASSESSMENTS);
  return baseRoutes(request);
}

// ---------------------------------------------------------- mark entry (P4-12)

export const MARK_STUDENTS = [
  {
    studentId: "stu-1",
    studentNumber: "STU-2026-0001",
    studentName: "Abel Bekele",
    rollNumber: "1",
  },
  {
    studentId: "stu-2",
    studentNumber: "STU-2026-0002",
    studentName: "Sara Tesfaye",
    rollNumber: "2",
  },
  {
    studentId: "stu-3",
    studentNumber: "STU-2026-0003",
    studentName: "Miki Alemu",
    rollNumber: "3",
  },
];

function assessment(
  id: string,
  title: string,
  component: string,
  componentId: string,
  maxPoints: string,
  outOf: string,
  date: string,
): AssessmentListItem {
  return {
    id,
    title,
    year_id: "year-1",
    year_code: "2026",
    term_id: "term-1",
    term_name: "Semester 1",
    section_id: "sec-1",
    section_code: "G5A",
    level_id: "lvl-1",
    level_name: "Grade 5",
    subject_id: "sub-1",
    subject_name: "Mathematics",
    component_id: componentId,
    component_name: component,
    component_key: component.toLowerCase().replace(/\s+/g, "-"),
    component_max_points: maxPoints,
    assessment_date: date,
    out_of: outOf,
    allow_bonus: false,
    status: "active",
    scores: 0,
    entered: 0,
    row_version: 1,
  };
}

export const MARK_ASSESSMENTS = {
  items: [
    assessment(
      "exam-1",
      "Quiz 1",
      "Quizzes",
      "comp-1",
      "10",
      "15",
      "2026-10-05",
    ),
    assessment(
      "exam-2",
      "Quiz 2",
      "Quizzes",
      "comp-1",
      "10",
      "13",
      "2026-11-09",
    ),
    assessment(
      "exam-3",
      "Midterm",
      "Midterm exam",
      "comp-2",
      "30",
      "30",
      "2026-11-25",
    ),
  ],
  next_cursor: null,
  total: 3,
};

export function scoreItem(
  student: (typeof MARK_STUDENTS)[number],
  overrides: Record<string, unknown> = {},
) {
  return {
    score_id: null as string | null,
    student_id: student.studentId,
    student_number: student.studentNumber,
    student_name: student.studentName,
    student_name_am: null,
    roll_number: student.rollNumber,
    enrolled: true,
    raw_score: null as string | null,
    out_of: "15",
    status: "present" as const,
    converted: null as string | null,
    note: null,
    row_version: null as number | null,
    entered_at: null,
    ...overrides,
  };
}

export function scoreSheet(overrides: Partial<ScoreSheet> = {}): ScoreSheet {
  const sheet: ScoreSheet = {
    assessment_id: "exam-1",
    title: "Quiz 1",
    component_key: "quizzes",
    component_max_points: "10",
    out_of: "15",
    allow_bonus: false,
    editable: true,
    items: MARK_STUDENTS.map((student) => scoreItem(student)),
    stats: {
      total: MARK_STUDENTS.length,
      entered: 0,
      missing: MARK_STUDENTS.length,
      present: 0,
      absent: 0,
      excused: 0,
      exempt: 0,
      not_taken: 0,
      out_of: "15",
      component_max_points: "10",
      average_converted: null,
      average_percent: null,
      highest_converted: null,
      lowest_converted: null,
    },
    ...overrides,
  };
  return sheet;
}

export function markingWindow(
  overrides: Partial<MarkingWindow> = {},
): MarkingWindow {
  return {
    id: "window-1",
    year_id: "year-1",
    term_id: "term-1",
    level_id: null,
    section_id: "sec-1",
    scope_key: "section:sec-1",
    opens_at: "2026-10-01T00:00:00Z",
    closes_at: "2027-01-01T00:00:00Z",
    is_active: true,
    state: "open",
    note: null,
    row_version: 1,
    ...overrides,
  };
}

export function markSubmission(
  overrides: Partial<Submission> = {},
): Submission {
  return {
    id: "submission-1",
    year_id: "year-1",
    year_code: "2026",
    term_id: "term-1",
    section_id: "sec-1",
    section_code: "G5A",
    subject_id: "sub-1",
    subject_name: "Mathematics",
    status: "draft",
    submitted_at: null,
    approved_at: null,
    published_at: null,
    locked_at: null,
    note: null,
    assessments: 3,
    scores: 0,
    entered: 0,
    row_version: 1,
    ...overrides,
  };
}

export interface MarkRouteOptions {
  assessments?: typeof MARK_ASSESSMENTS;
  sheets?: Record<string, ScoreSheet>;
  windows?: MarkingWindow[];
  submissions?: Submission[];
  saved?: MockRequest[];
  onSave?: (request: MockRequest) => Response | null;
}

/** Routes for the mark-entry grid: assessments, sheets, windows, submissions. */
export function markRoutes(
  request: MockRequest,
  options: MarkRouteOptions = {},
): Response {
  const { url, method, body } = request;
  const sheets = options.sheets ?? {};

  const scores = url.match(
    /\/api\/v1\/assessment\/assessments\/([^/]+)\/scores$/,
  );
  if (scores) {
    const assessmentId = scores[1];
    if (method === "PUT") {
      options.saved?.push(request);
      const custom = options.onSave?.(request);
      if (custom) return custom;
      const changes = ((body?.items as Record<string, unknown>[]) ?? []).map(
        (item) => item,
      );
      const base =
        sheets[assessmentId] ?? scoreSheet({ assessment_id: assessmentId });
      const updated: ScoreSheet = {
        ...base,
        items: base.items.map((item) => {
          const change = changes.find(
            (entry) => entry.student_id === item.student_id,
          );
          if (!change) return item;
          const raw = (change.raw_score as string | null) ?? null;
          const converted =
            raw === null
              ? null
              : String(
                  Math.round(
                    (Number(raw) / Number(base.out_of)) *
                      Number(base.component_max_points) *
                      100,
                  ) / 100,
                );
          return {
            ...item,
            score_id:
              item.score_id ?? `score-${assessmentId}-${item.student_id}`,
            raw_score: raw,
            status: change.status as ScoreSheet["items"][number]["status"],
            converted,
            row_version: (item.row_version ?? 0) + 1,
            entered_at: "2026-11-19T00:00:00Z",
          };
        }),
      };
      sheets[assessmentId] = updated;
      return json({
        sheet: updated,
        created: 0,
        updated: changes.length,
        unchanged: 0,
      });
    }
    return json(
      sheets[assessmentId] ?? scoreSheet({ assessment_id: assessmentId }),
    );
  }
  if (url.includes("/api/v1/assessment/windows")) {
    const windows = options.windows ?? [markingWindow()];
    return json({ items: windows, next_cursor: null, total: windows.length });
  }
  if (url.includes("/api/v1/assessment/submissions")) {
    const submissions = options.submissions ?? [markSubmission()];
    return json({
      items: submissions,
      next_cursor: null,
      total: submissions.length,
    });
  }
  if (url.endsWith("/api/v1/assessment/corrections") && method === "POST") {
    options.saved?.push(request);
    return json({ id: "correction-1", status: "pending" }, 201);
  }
  if (url.includes("/api/v1/assessment/assessments")) {
    return json(options.assessments ?? MARK_ASSESSMENTS);
  }
  return baseRoutes(request);
}

export function threeSheets(): Record<string, ScoreSheet> {
  return {
    "exam-1": scoreSheet(),
    "exam-2": scoreSheet({
      assessment_id: "exam-2",
      title: "Quiz 2",
      out_of: "13",
    }),
    "exam-3": scoreSheet({
      assessment_id: "exam-3",
      title: "Midterm",
      out_of: "30",
      component_max_points: "30",
    }),
  };
}

export function openMarks() {
  return null;
}

// ---------------------------------------------------- manager dashboard (P4-14)

export function dashboardRow(
  overrides: Partial<DashboardRow> = {},
): DashboardRow {
  return {
    section_id: "sec-1",
    section_code: "G5A",
    level_id: "lvl-1",
    level_name: "Grade 5",
    subject_id: "sub-1",
    subject_name: "Mathematics",
    teachers: [{ staff_id: "staff-1", name: "Hanna Girma" }],
    assessments: 3,
    students: 10,
    expected: 30,
    entered: 21,
    missing: 9,
    completion_percent: "70",
    status: "draft",
    deadline: "2026-11-30T00:00:00Z",
    window_state: "open",
    overdue: false,
    ...overrides,
  };
}

export function dashboardAnomaly(
  overrides: Partial<DashboardAnomaly> = {},
): DashboardAnomaly {
  return {
    kind: "identical",
    assessment_id: "exam-1",
    title: "Quiz 1",
    section_id: "sec-1",
    section_code: "G5A",
    subject_id: "sub-1",
    subject_name: "Mathematics",
    count: 10,
    value: "5",
    threshold: "5",
    average_percent: null,
    norm_percent: null,
    ...overrides,
  };
}

export function dashboard(overrides: Partial<DashboardOut> = {}): DashboardOut {
  return {
    year_id: "year-1",
    term_id: "term-1",
    rows: [dashboardRow()],
    anomalies: [],
    summary: {
      sections: 1,
      assessments: 3,
      expected: 30,
      entered: 21,
      completion_percent: "70",
      overdue: 0,
      anomalies: 0,
    },
    ...overrides,
  };
}

export interface DashboardRouteOptions {
  data?: DashboardOut;
  reminded?: MockRequest[];
}

/** Routes for the progress dashboard: the read model and the reminder action. */
export function dashboardRoutes(
  request: MockRequest,
  options: DashboardRouteOptions = {},
): Response {
  const { url, method } = request;
  if (url.includes("/api/v1/assessment/dashboard/remind")) {
    if (method !== "POST") throw new Error(`Unexpected ${method} ${url}`);
    options.reminded?.push(request);
    return json({
      rows: 1,
      sent: 1,
      skipped: 0,
      recipients: [
        {
          user_id: "user-1",
          staff_id: "staff-1",
          name: "Hanna Girma",
          section_id: "sec-1",
          subject_id: "sub-1",
        },
      ],
    });
  }
  if (url.includes("/api/v1/assessment/dashboard")) {
    return json(options.data ?? dashboard());
  }
  return baseRoutes(request);
}
