import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { AppProviders, AppRoutes } from "../../App";

export const MESSAGES: Record<string, string> = {
  "app.name": "School ERP",
  "app.short_name": "ERP",
  "nav.dashboard": "Dashboard",
  "nav.activity": "Activity history",
  "nav.academics": "Academics",
  "auth.logout": "Sign out",
  "common.loading": "Loading…",
  "common.error": "Something went wrong",
  "common.enabled": "Enabled",
  "common.disabled": "Disabled",
  "academics.title": "Academic structure",
  "academics.intro": "Grade levels, years and sections.",
  "academics.permission_denied": "You do not have permission to view academic structure.",
  "academics.setup.title": "Setup checklist",
  "academics.setup.intro": "Work through these steps once for the school.",
  "academics.setup.progress": "{{done}} of {{total}} steps complete",
  "academics.setup.complete": "Setup complete — academics is ready for admissions.",
  "academics.setup.open": "Open",
  "academics.setup.status.done": "Done",
  "academics.setup.status.pending": "To do",
  "academics.setup.manage_hint": "You can review this setup, but changing it needs the academics manage permission.",
  "academics.setup.step.scope": "Set the school scope",
  "academics.setup.step.scope_hint": "Choose the first and last grade level this school runs.",
  "academics.setup.step.curriculum": "Choose a curriculum profile",
  "academics.setup.step.curriculum_hint": "Review a starter profile, then apply it to a year.",
  "academics.setup.step.years": "Create and open an academic year",
  "academics.setup.step.years_hint": "Define the year and its terms.",
  "academics.setup.step.subjects": "Assign subjects to levels",
  "academics.setup.step.subjects_hint": "Choose what each level offers.",
  "academics.setup.step.sections": "Create sections",
  "academics.setup.step.sections_hint": "Split each level into sections.",
  "academics.tab.setup": "Setup",
  "academics.tab.scope": "Scope",
  "academics.tab.curriculum": "Curriculum",
  "academics.tab.years": "Years & terms",
  "academics.tab.subjects": "Subjects",
  "academics.tab.sections": "Sections",
  "academics.scope": "School scope",
  "academics.scope.hint": "The scope limits every grade-level list.",
  "academics.scope.first_level": "First grade level",
  "academics.scope.last_level": "Last grade level",
  "academics.scope.reason": "Reason (optional)",
  "academics.scope.save": "Save scope",
  "academics.scope.saving": "Saving…",
  "academics.scope.saved": "Academic scope updated",
  "academics.scope.starter_hint": "Starter levels are marked until confirmed.",
  "academics.scope.levels_count": "{{count}} levels in scope",
  "academics.scope.stages_count": "{{count}} stages",
  "academics.levels": "Grade levels",
  "academics.verify_hint": "Starter data — verify it.",
  "academics.empty.levels": "No grade levels yet",
  "academics.empty.years": "No academic years yet",
  "academics.empty.subjects": "No subjects yet",
  "academics.empty.sections": "No sections yet",
  "academics.empty.subject_groups": "No subject groups yet",
  "academics.years": "Academic years",
  "academics.term_system.semester": "Semesters",
  "academics.term_system.quarter": "Quarters",
  "academics.year.create_title": "New academic year",
  "academics.year.create_hint": "A year starts as a draft.",
  "academics.year.create": "Create year",
  "academics.year.creating": "Creating…",
  "academics.year.list_hint": "Open exactly one year at a time.",
  "academics.year.code": "Code",
  "academics.year.name": "Name (English)",
  "academics.year.name_am": "Name (Amharic)",
  "academics.year.start_date": "Starts",
  "academics.year.end_date": "Ends",
  "academics.year.profile": "Curriculum profile",
  "academics.year.no_profile": "No curriculum profile",
  "academics.year.profile_hint": "The profile uses {{term_system}}.",
  "academics.year.current": "Current year",
  "academics.year.draft": "Draft",
  "academics.year.open": "Open",
  "academics.year.closed": "Closed",
  "academics.year.open_action": "Open year",
  "academics.year.close_action": "Close year",
  "academics.term.pending": "Not started",
  "academics.term.open": "Open",
  "academics.term.closed": "Closed",
  "academics.term.open_action": "Open term",
  "academics.term.close_action": "Close term",
  "academics.subjects": "Subjects",
  "academics.subject.create_title": "Subjects",
  "academics.subject.create_hint": "Subjects are school-wide.",
  "academics.subject.create": "Add subject",
  "academics.subject.creating": "Adding…",
  "academics.subject.code": "Code",
  "academics.subject.name": "Name (English)",
  "academics.subject.name_am": "Name (Amharic)",
  "academics.subject.assign_title": "Subjects by level",
  "academics.subject.assign_hint": "Choose a level and tick its subjects.",
  "academics.subject.select_level": "Select a grade level",
  "academics.subject.choose_level": "Choose a level to see and edit its subjects.",
  "academics.subject.assign_save": "Save subjects",
  "academics.subject.assign_saving": "Saving…",
  "academics.subject.credit": "Credit",
  "academics.subject_groups": "Subject groups",
  "academics.subject.group_hint": "Groups bundle subjects for electives.",
  "academics.subject.group_code": "Group code",
  "academics.subject.group_create": "Add group",
  "academics.subject.group_creating": "Adding…",
  "academics.subject_group.name": "Group name",
  "academics.subject_group.members": "Subjects in this group",
  "academics.sections": "Sections",
  "academics.section.create_title": "New section",
  "academics.section.create_hint": "Sections belong to one level in one year.",
  "academics.section.create": "Add section",
  "academics.section.creating": "Adding…",
  "academics.section.delete": "Delete",
  "academics.section.list_hint": "Closed years cannot change.",
  "academics.section.year": "Academic year",
  "academics.section.level": "Grade level",
  "academics.section.code": "Section code",
  "academics.section.name": "Name (English)",
  "academics.section.name_am": "Name (Amharic)",
  "academics.section.capacity": "Capacity",
  "academics.section.homeroom": "Homeroom teacher",
  "academics.section.homeroom_none": "No homeroom teacher",
  "academics.curriculum.title": "Curriculum profiles",
  "academics.curriculum.starter_warning": "Starter profiles are examples.",
  "academics.curriculum.unverified": "Starter — verify",
  "academics.curriculum.verified": "Verified",
  "academics.curriculum.starter": "Starter",
  "academics.curriculum.in_use": "In use",
  "academics.curriculum.not_in_use": "Not in use",
  "academics.curriculum.select_hint": "Choose a profile.",
  "academics.curriculum.name": "Profile name",
  "academics.curriculum.name_am": "Profile name (Amharic)",
  "academics.curriculum.description": "Description",
  "academics.curriculum.save": "Save profile",
  "academics.curriculum.saving": "Saving…",
  "academics.curriculum.levels": "Subjects by level",
  "academics.curriculum.no_levels": "This profile has no level subjects yet.",
  "academics.curriculum.duplicate_hint": "Duplicate this profile.",
  "academics.curriculum.duplicate_code": "New code",
  "academics.curriculum.duplicate_name": "New name",
  "academics.curriculum.duplicate": "Duplicate",
  "academics.curriculum.duplicating": "Duplicating…",
  "academics.curriculum.apply_title": "Apply to an academic year",
  "academics.curriculum.apply_hint": "Preview first.",
  "academics.curriculum.apply_year": "Academic year",
  "academics.curriculum.preview": "Preview changes",
  "academics.curriculum.previewing": "Previewing…",
  "academics.curriculum.apply": "Apply profile",
  "academics.curriculum.applying": "Applying…",
  "academics.curriculum.term_match": "Term systems match.",
  "academics.curriculum.term_mismatch": "Term systems do not match.",
  "academics.curriculum.changes": "{{count}} levels change",
  "academics.curriculum.credits_changed": "Credits changed",
  "academics.curriculum.applied": "Applied",
};

export interface MockRequest {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}

export function json(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    headers: { get: () => null },
  } as unknown as Response;
}

export function session(permissions: string[]) {
  return {
    id: "u-admin",
    email: "superadmin@demo.school",
    display_name: "Super Admin",
    locale: "en",
    roles: ["super_admin"],
    permissions,
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [
      { key: "dashboard", label_key: "nav.dashboard", path: "/", module: "core" },
      { key: "academics", label_key: "nav.academics", path: "/academics", module: "academics" },
    ],
    modules: ["academics"],
    locale: "en",
    languages: ["en", "am"],
  };
}

export function stubAcademics(
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

export function renderAcademics() {
  return render(
    <AppProviders
      initialMessages={MESSAGES}
      queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={["/academics"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

export const SCOPE = {
  first_level: 0,
  last_level: 12,
  level_count: 13,
  stage_count: 3,
  scope_levels: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
};

export function level(overrides: Record<string, unknown> = {}) {
  return {
    id: "lvl-1",
    code: "grade-1",
    name: "Grade 1",
    name_am: "አንደኛ ክፍል",
    scope_level: 1,
    sort_order: 2,
    is_active: true,
    is_starter: true,
    is_verified: false,
    in_scope: true,
    row_version: 1,
    ...overrides,
  };
}

export const LEVELS = {
  items: [level(), level({ id: "lvl-2", code: "grade-2", name: "Grade 2", scope_level: 2, sort_order: 3 })],
  total: 2,
  scope: SCOPE,
};

export function term(overrides: Record<string, unknown> = {}) {
  return {
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
    ...overrides,
  };
}

export function year(overrides: Record<string, unknown> = {}) {
  return {
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
    terms: [term()],
    row_version: 1,
    ...overrides,
  };
}

export const YEARS = { items: [year()], total: 1, current_year_id: "year-1" };

export function subject(overrides: Record<string, unknown> = {}) {
  return {
    id: "sub-math",
    code: "math",
    name: "Mathematics",
    name_am: "ሒሳብ",
    sort_order: 1,
    is_active: true,
    row_version: 1,
    ...overrides,
  };
}

export const SUBJECTS = {
  items: [subject(), subject({ id: "sub-art", code: "art", name: "Art", name_am: "ሥነ ጥበብ", sort_order: 2 })],
  total: 2,
};

export function assignedSubject(overrides: Record<string, unknown> = {}) {
  return {
    subject_id: "sub-math",
    code: "math",
    name: "Mathematics",
    name_am: "ሒሳብ",
    credit: 1,
    is_active: true,
    ...overrides,
  };
}

export function section(overrides: Record<string, unknown> = {}) {
  return {
    id: "sec-1",
    year_id: "year-1",
    year_code: "2026",
    level_id: "lvl-1",
    level_code: "grade-1",
    level_name: "Grade 1",
    code: "A",
    name: "Section A",
    name_am: null,
    capacity: 40,
    homeroom_user_id: null,
    homeroom_name: null,
    is_active: true,
    row_version: 1,
    ...overrides,
  };
}

export function profile(overrides: Record<string, unknown> = {}) {
  return {
    id: "profile-1",
    code: "national",
    name: "National curriculum",
    name_am: "ብሔራዊ ስርዓተ ትምህርት",
    description: "Starter profile",
    term_system: "semester",
    sort_order: 1,
    is_active: true,
    is_starter: true,
    is_verified: false,
    in_use: false,
    levels: [
      {
        level_id: "lvl-1",
        level_code: "grade-1",
        level_name: "Grade 1",
        subjects: [assignedSubject()],
        total: 1,
      },
    ],
    row_version: 1,
    ...overrides,
  };
}

export const PROFILES = { items: [profile()], total: 1 };

export function applyResult(overrides: Record<string, unknown> = {}) {
  return {
    year_id: "year-1",
    year_code: "2026",
    profile_id: "profile-1",
    profile_code: "national",
    profile_name: "National curriculum",
    profile_term_system: "semester",
    year_term_system: "semester",
    term_system_matches: true,
    applied: false,
    levels_changed: 2,
    assignments_added: 5,
    assignments_removed: 1,
    credits_changed: 0,
    changed_levels: ["Grade 1", "Grade 2"],
    skipped_inactive_subjects: [],
    ...overrides,
  };
}
