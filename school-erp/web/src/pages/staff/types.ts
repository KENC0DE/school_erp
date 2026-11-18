export type StaffStatus = "active" | "on_leave" | "suspended" | "terminated";

export const STAFF_STATUSES: readonly StaffStatus[] = [
  "active",
  "on_leave",
  "suspended",
  "terminated",
];

export type ContractType =
  | "permanent"
  | "fixed_term"
  | "part_time"
  | "temporary"
  | "internship";

export type ContractStatus = "draft" | "active" | "ended";

export type QualificationKind =
  | "education"
  | "training"
  | "certification"
  | "experience";

export const CONTRACT_TYPES: readonly ContractType[] = [
  "permanent",
  "fixed_term",
  "part_time",
  "temporary",
  "internship",
];

export const CONTRACT_STATUSES: readonly ContractStatus[] = [
  "draft",
  "active",
  "ended",
];

export const QUALIFICATION_KINDS: readonly QualificationKind[] = [
  "education",
  "training",
  "certification",
  "experience",
];

export interface StaffPerson {
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

export interface Department {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  parent_id: string | null;
  description: string | null;
  is_active: boolean;
  sort_order: number;
  row_version: number;
}

export interface DepartmentList {
  items: Department[];
  total: number;
}

export interface Position {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  department_id: string | null;
  department_code: string | null;
  department_name: string | null;
  is_teaching: boolean;
  description: string | null;
  is_active: boolean;
  sort_order: number;
  row_version: number;
}

export interface PositionList {
  items: Position[];
  total: number;
}

export interface StaffSummary {
  id: string;
  staff_number: string;
  status: StaffStatus;
  person: StaffPerson;
  user_id: string | null;
  department: Department | null;
  position: Position | null;
  hire_date: string | null;
  end_date: string | null;
  row_version: number;
}

export interface StaffList {
  items: StaffSummary[];
  next_cursor: string | null;
  total: number;
}

export interface Contract {
  id: string;
  staff_id: string;
  type: ContractType;
  status: ContractStatus;
  start_date: string;
  end_date: string | null;
  salary_santim: number | null;
  notes: string | null;
  row_version: number;
}

export interface ContractList {
  items: Contract[];
  total: number;
}

export interface Qualification {
  id: string;
  staff_id: string;
  kind: QualificationKind;
  title: string;
  institution: string | null;
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
  result: string | null;
  notes: string | null;
  row_version: number;
}

export interface QualificationList {
  items: Qualification[];
  total: number;
}

export interface StaffDetail extends StaffSummary {
  notes: string | null;
  custom: Record<string, unknown>;
  contracts: Contract[];
  contracts_restricted: boolean;
  qualifications: Qualification[];
}

export interface TeachingAssignment {
  id: string;
  staff_id: string;
  staff_number: string;
  year_id: string;
  year_code: string;
  section_id: string;
  section_code: string;
  section_name: string | null;
  level_id: string;
  level_code: string;
  level_name: string;
  subject_id: string;
  subject_code: string;
  subject_name: string;
  notes: string | null;
  row_version: number;
}

export interface TeachingAssignmentList {
  items: TeachingAssignment[];
  total: number;
}

export type LeaveStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "rejected"
  | "cancelled";

export const LEAVE_STATUSES: readonly LeaveStatus[] = [
  "draft",
  "submitted",
  "approved",
  "rejected",
  "cancelled",
];

export interface LeaveType {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  is_paid: boolean;
  annual_entitlement_days: number;
  counts_against_balance: boolean;
  requires_approval: boolean;
  is_active: boolean;
  sort_order: number;
  notes: string | null;
  row_version: number;
}

export interface LeaveTypeList {
  items: LeaveType[];
  total: number;
}

export interface LeaveBalance {
  id: string;
  staff_id: string;
  staff_number: string;
  staff_name: string;
  year_id: string;
  year_code: string;
  leave_type_id: string;
  leave_type_code: string;
  leave_type_name: string;
  entitled_days: number;
  carried_days: number;
  adjustment_days: number;
  used_days: number;
  pending_days: number;
  remaining_days: number;
  notes: string | null;
  row_version: number;
}

export interface LeaveBalanceList {
  items: LeaveBalance[];
  total: number;
}

export interface LeaveRequest {
  id: string;
  staff_id: string;
  staff_number: string;
  staff_name: string;
  year_id: string;
  year_code: string;
  leave_type_id: string;
  leave_type_code: string;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  is_half_day: boolean;
  days: number;
  reason: string | null;
  status: LeaveStatus;
  submitted_at: string | null;
  decided_at: string | null;
  decided_by: string | null;
  decided_by_name: string | null;
  decision_note: string | null;
  row_version: number;
}

export interface LeaveRequestList {
  items: LeaveRequest[];
  total: number;
}

export interface LeaveCalendar {
  from_date: string;
  to_date: string;
  items: LeaveRequest[];
  total: number;
}

export interface UploadedStaffDocument {
  id: string;
  name: string;
  mime: string;
  size_bytes: number;
  url: string;
}

export interface DocumentList {
  items: UploadedStaffDocument[];
}

export interface StaffFilters {
  q: string;
  status: string;
  department_id: string;
  position_id: string;
}

export const EMPTY_FILTERS: StaffFilters = {
  q: "",
  status: "",
  department_id: "",
  position_id: "",
};
