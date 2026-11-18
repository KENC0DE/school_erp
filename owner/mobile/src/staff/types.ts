export type StaffStatus = "active" | "on_leave" | "suspended" | "terminated";

export const STAFF_STATUSES: readonly StaffStatus[] = [
  "active",
  "on_leave",
  "suspended",
  "terminated",
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

export interface StaffDepartment {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  is_active: boolean;
}

export interface StaffPosition {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  department_id: string | null;
  is_teaching: boolean;
  is_active: boolean;
}

export interface StaffSummary {
  id: string;
  staff_number: string;
  status: StaffStatus;
  person: StaffPerson;
  user_id: string | null;
  department: StaffDepartment | null;
  position: StaffPosition | null;
  hire_date: string | null;
  end_date: string | null;
  row_version: number;
}

export interface StaffDetail extends StaffSummary {
  notes: string | null;
}

export interface StaffList {
  items: StaffSummary[];
  next_cursor: string | null;
  total: number;
}

export interface StaffFilters {
  q?: string;
  status?: string;
}
