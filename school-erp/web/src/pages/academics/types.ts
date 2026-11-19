export interface ScopeView {
  first_level: number;
  last_level: number;
  level_count: number;
  stage_count: number;
  scope_levels: number[];
}

export interface Level {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  scope_level: number;
  sort_order: number;
  is_active: boolean;
  is_starter: boolean;
  is_verified: boolean;
  in_scope: boolean;
  row_version: number;
}

export interface LevelList {
  items: Level[];
  total: number;
  scope: ScopeView;
}

export type YearStatus = "draft" | "open" | "closed";
export type TermStatus = "pending" | "open" | "closed";
export type TermSystem = "semester" | "quarter";

export interface Term {
  id: string;
  year_id: string;
  number: number;
  name: string;
  name_am: string | null;
  start_date: string;
  end_date: string;
  start_date_display: string;
  end_date_display: string;
  status: TermStatus;
  row_version: number;
}

export interface Year {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  start_date: string;
  end_date: string;
  start_date_display: string;
  end_date_display: string;
  term_system: TermSystem;
  status: YearStatus;
  current_term_id: string | null;
  curriculum_profile_id: string | null;
  curriculum_profile_code: string | null;
  terms: Term[];
  row_version: number;
}

export interface YearList {
  items: Year[];
  total: number;
  current_year_id: string | null;
}

export interface Subject {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  sort_order: number;
  is_active: boolean;
  row_version: number;
}

export interface SubjectList {
  items: Subject[];
  total: number;
}

export interface AssignedSubject {
  subject_id: string;
  code: string;
  name: string;
  name_am: string | null;
  credit: number;
  is_active: boolean;
}

export interface LevelSubjects {
  level_id: string;
  level_code: string;
  items: AssignedSubject[];
  total: number;
}

export interface SubjectGroup {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  sort_order: number;
  is_active: boolean;
  subjects: Subject[];
  row_version: number;
}

export interface SubjectGroupList {
  items: SubjectGroup[];
  total: number;
}

export interface Section {
  id: string;
  year_id: string;
  year_code: string;
  level_id: string;
  level_code: string;
  level_name: string;
  code: string;
  name: string | null;
  name_am: string | null;
  capacity: number;
  homeroom_user_id: string | null;
  homeroom_name: string | null;
  is_active: boolean;
  row_version: number;
}

export interface SectionList {
  items: Section[];
  total: number;
}

export interface CurriculumLevel {
  level_id: string;
  level_code: string;
  level_name: string;
  subjects: AssignedSubject[];
  total: number;
}

export interface CurriculumProfile {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  description: string | null;
  term_system: TermSystem;
  sort_order: number;
  is_active: boolean;
  is_starter: boolean;
  is_verified: boolean;
  in_use: boolean;
  levels: CurriculumLevel[];
  row_version: number;
}

export interface CurriculumProfileList {
  items: CurriculumProfile[];
  total: number;
}

export interface CurriculumApplyResult {
  year_id: string;
  year_code: string;
  profile_id: string;
  profile_code: string;
  profile_name: string;
  profile_term_system: TermSystem;
  year_term_system: TermSystem;
  term_system_matches: boolean;
  applied: boolean;
  levels_changed: number;
  assignments_added: number;
  assignments_removed: number;
  credits_changed: number;
  changed_levels: string[];
  skipped_inactive_subjects: string[];
}

export interface UserOption {
  id: string;
  display_name: string;
  email: string;
  is_active: boolean;
}

export interface UserList {
  items: UserOption[];
  next_cursor: string | null;
}

export type Panel =
  | "setup"
  | "scope"
  | "years"
  | "subjects"
  | "sections"
  | "curriculum";
