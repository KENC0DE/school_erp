import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import coreEn from "../../../../backend/core/i18n/en.json";
import staffEn from "../../../../backend/modules/staff/i18n/en.json";
import { AppProviders, AppRoutes } from "../../App";
import type { LeaveRequest } from "./types";

export const staffMessages: Record<string, string> = {
  ...coreEn,
  ...Object.fromEntries(
    Object.entries(staffEn).map(([key, value]) => [`staff.${key}`, value]),
  ),
};

export const STAFF_ID = "staff-1";

export interface MockRequest {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}

export const DEPARTMENT = {
  id: "dept-1",
  code: "science",
  name: "Science",
  name_am: null,
  parent_id: null,
  description: null,
  is_active: true,
  sort_order: 0,
  row_version: 1,
};

export const POSITION = {
  id: "position-1",
  code: "teacher",
  name: "Teacher",
  name_am: null,
  department_id: "dept-1",
  department_code: "science",
  department_name: "Science",
  is_teaching: true,
  description: null,
  is_active: true,
  sort_order: 0,
  row_version: 1,
};

export const PERSON = {
  id: "person-1",
  given_name_en: "Abebe",
  father_name_en: "Bekele",
  grandfather_name_en: "Tesfaye",
  given_name_am: "አበበ",
  father_name_am: "በቀለ",
  grandfather_name_am: "ተስፋዬ",
  sex: "male",
  date_of_birth: "1985-04-12",
  phone: "0911000000",
  email: "abebe@demo.school",
  address: "Addis Ababa",
  full_name: "Abebe Bekele Tesfaye",
  short_name: "Abebe Bekele",
  row_version: 1,
};

export const STAFF = {
  id: STAFF_ID,
  staff_number: "STF-2026-0001",
  status: "active" as const,
  person: PERSON,
  user_id: null,
  department: DEPARTMENT,
  position: POSITION,
  hire_date: "2020-09-01",
  end_date: null,
  row_version: 1,
};

export const STAFF_DETAIL = {
  ...STAFF,
  notes: "Head of science.",
  custom: {},
  contracts: [],
  contracts_restricted: true,
  qualifications: [],
};

export const CONTRACT = {
  id: "contract-1",
  staff_id: STAFF_ID,
  type: "permanent" as const,
  status: "active" as const,
  start_date: "2024-09-01",
  end_date: null,
  salary_santim: 1500000,
  notes: null,
  row_version: 1,
};

export const LEAVE_TYPE = {
  id: "leave-type-1",
  code: "annual",
  name: "Annual leave",
  name_am: null,
  is_paid: true,
  annual_entitlement_days: 20,
  counts_against_balance: true,
  requires_approval: true,
  is_active: true,
  sort_order: 0,
  notes: null,
  row_version: 1,
};

export const YEAR = {
  id: "year-1",
  code: "2026",
  name: "2026/27",
  name_am: null,
  start_date: "2026-09-01",
  end_date: "2027-06-30",
  start_date_display: "2026-09-01",
  end_date_display: "2027-06-30",
  term_system: "semester" as const,
  status: "open" as const,
  current_term_id: null,
  curriculum_profile_id: null,
  curriculum_profile_code: null,
  terms: [],
  row_version: 1,
};

export const LEAVE_BALANCE = {
  id: "balance-1",
  staff_id: STAFF_ID,
  staff_number: "STF-2026-0001",
  staff_name: "Abebe Bekele Tesfaye",
  year_id: "year-1",
  year_code: "2026",
  leave_type_id: "leave-type-1",
  leave_type_code: "annual",
  leave_type_name: "Annual leave",
  entitled_days: 20,
  carried_days: 0,
  adjustment_days: 0,
  used_days: 2,
  pending_days: 1,
  remaining_days: 17,
  notes: null,
  row_version: 1,
};

export const LEAVE_REQUEST: LeaveRequest = {
  id: "request-1",
  staff_id: STAFF_ID,
  staff_number: "STF-2026-0001",
  staff_name: "Abebe Bekele Tesfaye",
  year_id: "year-1",
  year_code: "2026",
  leave_type_id: "leave-type-1",
  leave_type_code: "annual",
  leave_type_name: "Annual leave",
  start_date: "2026-10-05",
  end_date: "2026-10-06",
  is_half_day: false,
  days: 2,
  reason: "Family event",
  status: "draft" as const,
  submitted_at: null,
  decided_at: null,
  decided_by: null,
  decided_by_name: null,
  decision_note: null,
  row_version: 1,
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
    email: "hr@demo.school",
    display_name: "HR Lead",
    locale: "en",
    roles: ["school_admin"],
    permissions,
    is_controller: false,
  };
}

export function navigation() {
  return {
    items: [{ key: "staff", label_key: "staff.nav", path: "/staff", module: "staff" }],
    modules: ["staff"],
    locale: "en",
    languages: ["en", "am"],
  };
}

export function renderAt(path: string) {
  return render(
    <AppProviders
      initialMessages={staffMessages}
      queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}
