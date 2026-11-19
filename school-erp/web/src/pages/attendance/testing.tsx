import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import coreEn from "../../../../backend/core/i18n/en.json";
import attendanceEn from "../../../../backend/modules/attendance/i18n/en.json";
import { AppProviders, AppRoutes } from "../../App";
import type { SessionDetail, SessionSummary } from "./types";

export const attendanceMessages: Record<string, string> = {
  ...coreEn,
  ...Object.fromEntries(
    Object.entries(attendanceEn).map(([key, value]) => [`attendance.${key}`, value]),
  ),
};

export const YEAR = {
  id: "year-1",
  code: "2026",
  name: "2026/27",
  status: "open",
};

export const LEVEL = {
  id: "level-1",
  code: "g5",
  name: "Grade 5",
  scope_level: 5,
  in_scope: true,
};

export const SECTION = {
  id: "section-1",
  year_id: "year-1",
  level_id: "level-1",
  code: "A",
  name: "Grade 5 A",
  is_active: true,
};

export const COUNTS = { total: 3, present: 2, absent: 1, late: 0, excused: 0 };

export const SESSION: SessionSummary = {
  id: "session-1",
  year_id: "year-1",
  year_code: "2026",
  section_id: "section-1",
  section_code: "A",
  section_name: "Grade 5 A",
  level_id: "level-1",
  level_code: "g5",
  level_name: "Grade 5",
  date: "2026-10-01",
  mode: "daily",
  period: null,
  subject_id: null,
  subject_code: null,
  subject_name: null,
  status: "open",
  notes: null,
  counts: COUNTS,
  status_changed_at: null,
  status_changed_by: null,
  status_changed_by_name: null,
  row_version: 1,
};

function record(
  id: string,
  studentId: string,
  name: string,
  number: string,
  status: "present" | "absent" | "late" | "excused",
) {
  return {
    id,
    session_id: "session-1",
    student_id: studentId,
    student_number: number,
    student_name: name,
    student_name_am: null,
    roll_number: number.slice(-1),
    status,
    reason: status === "absent" ? "Sick" : null,
    late_minutes: null,
    note: null,
    recorded_at: "2026-10-01T08:00:00Z",
    recorded_by: "u-1",
    recorded_by_name: "Attendance Lead",
    row_version: 1,
  };
}

export const DETAIL: SessionDetail = {
  ...SESSION,
  records: [
    record("record-1", "student-1", "Abebe Bekele Tesfaye", "S-1", "present"),
    record("record-2", "student-2", "Hana Desta Alemu", "S-2", "absent"),
    record("record-3", "student-3", "Dawit Kebede Tessema", "S-3", "present"),
  ],
  roster: [
    {
      student_id: "student-1",
      student_number: "S-1",
      full_name: "Abebe Bekele Tesfaye",
      roll_number: "1",
      status: "present",
      record_id: "record-1",
    },
    {
      student_id: "student-2",
      student_number: "S-2",
      full_name: "Hana Desta Alemu",
      roll_number: "2",
      status: "absent",
      record_id: "record-2",
    },
    {
      student_id: "student-3",
      student_number: "S-3",
      full_name: "Dawit Kebede Tessema",
      roll_number: "3",
      status: "present",
      record_id: "record-3",
    },
  ],
};

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function session(permissions: string[]) {
  return {
    id: "u-1",
    email: "teacher@demo.school",
    display_name: "Attendance Lead",
    locale: "en",
    roles: ["school_admin"],
    permissions,
    is_controller: false,
  };
}

export function navigation() {
  return {
    items: [
      {
        key: "attendance",
        label_key: "attendance.nav",
        path: "/attendance",
        module: "attendance",
      },
    ],
    modules: ["attendance"],
    locale: "en",
    languages: ["en", "am"],
  };
}

export function renderAt(path: string) {
  return render(
    <AppProviders
      initialMessages={attendanceMessages}
      queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}
