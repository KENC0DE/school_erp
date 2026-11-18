export type StudentStatus =
  | "applicant"
  | "active"
  | "promoted"
  | "repeating"
  | "transferred_out"
  | "withdrawn"
  | "graduated"
  | "alumni";

export const STUDENT_STATUSES: readonly StudentStatus[] = [
  "applicant",
  "active",
  "promoted",
  "repeating",
  "transferred_out",
  "withdrawn",
  "graduated",
  "alumni",
];

export interface MobilePerson {
  id: string;
  given_name_en: string | null;
  father_name_en: string | null;
  grandfather_name_en: string | null;
  given_name_am: string | null;
  father_name_am: string | null;
  grandfather_name_am: string | null;
  sex: string | null;
  date_of_birth: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  full_name: string;
  short_name: string;
  row_version: number;
}

export interface MobileEnrollment {
  id: string;
  student_id: string;
  year_id: string;
  year_code: string | null;
  year_name: string | null;
  level_id: string;
  level_code: string | null;
  level_name: string | null;
  section_id: string | null;
  section_code: string | null;
  roll_number: string | null;
  status: StudentStatus;
  row_version: number;
}

export interface MobileGuardian {
  id: string;
  relationship: string;
  is_primary: boolean;
  can_pickup: boolean;
  person: MobilePerson;
}

export interface StudentSummary {
  id: string;
  student_number: string;
  status: StudentStatus;
  admission_date: string | null;
  person: MobilePerson;
  enrollment: MobileEnrollment | null;
  row_version: number;
}

export interface StudentDetail extends StudentSummary {
  exit_date: string | null;
  exit_reason: string | null;
  notes: string | null;
  enrollments: MobileEnrollment[];
  guardians: MobileGuardian[];
  medical: Record<string, unknown> | null;
}

export interface StudentList {
  items: StudentSummary[];
  next_cursor: string | null;
  total: number;
}

export interface AcademicYear {
  id: string;
  code: string;
  name: string;
  status: string;
}

export interface YearList {
  items: AcademicYear[];
  total: number;
  current_year_id: string | null;
}

export interface AcademicLevel {
  id: string;
  code: string;
  name: string;
  in_scope: boolean;
}

export interface LevelList {
  items: AcademicLevel[];
  total: number;
}

export interface AcademicSection {
  id: string;
  year_id: string;
  level_id: string;
  code: string;
  name: string | null;
}

export interface SectionList {
  items: AcademicSection[];
  total: number;
}

export interface DuplicateWarning {
  person: { full_name?: string };
  reason: string;
  similarity: number;
}

export interface RegistrationPreview {
  student_number: string;
  number_generated: boolean;
  full_name: string;
  duplicate_warnings: DuplicateWarning[];
  has_enrollment: boolean;
}

export interface PersonInput {
  given_name_en?: string;
  father_name_en?: string;
  grandfather_name_en?: string;
  given_name_am?: string;
  father_name_am?: string;
  grandfather_name_am?: string;
  sex?: string;
  date_of_birth?: string;
  phone?: string;
  address?: string;
}

export interface EnrollmentInput {
  year_id: string;
  level_id: string;
  section_id?: string;
}

export interface StudentRegistration {
  person: PersonInput;
  student_number?: string;
  admission_date?: string;
  enrollment?: EnrollmentInput;
}

export type StudentFilters = {
  q?: string;
  status?: string;
};
