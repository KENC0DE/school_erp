export type StudentStatus =
  | "applicant"
  | "active"
  | "promoted"
  | "repeating"
  | "transferred_out"
  | "withdrawn"
  | "graduated"
  | "alumni";

export interface Person {
  id: string;
  given_name_en: string | null;
  father_name_en: string | null;
  grandfather_name_en: string | null;
  given_name_am: string | null;
  father_name_am: string | null;
  grandfather_name_am: string | null;
  mother_name_en: string | null;
  mother_name_am: string | null;
  baptismal_name: string | null;
  nickname: string | null;
  sex: string | null;
  date_of_birth: string | null;
  place_of_birth: string | null;
  nationality: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  photo_file_id: string | null;
  custom: Record<string, unknown>;
  full_name: string;
  short_name: string;
  row_version: number;
}

export interface Enrollment {
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
  notes: string | null;
  row_version: number;
}

export interface Guardian {
  id: string;
  student_id: string;
  person_id: string;
  relationship: string;
  is_primary: boolean;
  can_pickup: boolean;
  notes: string | null;
  person: Person;
  row_version: number;
}

export interface Medical {
  id: string;
  student_id: string;
  blood_type: string | null;
  allergies: string | null;
  chronic_conditions: string | null;
  medications: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  notes: string | null;
  consent_to_treat: boolean;
  row_version: number;
}

export interface StudentSummary {
  id: string;
  student_number: string;
  status: StudentStatus;
  admission_date: string | null;
  person: Person;
  enrollment: Enrollment | null;
  row_version: number;
}

export interface StudentDetail extends StudentSummary {
  exit_date: string | null;
  exit_reason: string | null;
  notes: string | null;
  custom: Record<string, unknown>;
  enrollments: Enrollment[];
  guardians: Guardian[];
  medical: Medical | null;
}

export interface DuplicateWarning {
  person: Person;
  reason: "same_names_and_dob" | "similar_name_and_dob";
  similarity: number;
}

export interface StudentList {
  items: StudentSummary[];
  next_cursor: string | null;
  total: number;
}

export interface StudentRegisterOut extends StudentDetail {
  duplicate_warnings: DuplicateWarning[];
}

export interface StudentPhoto {
  file_id: string;
  name: string;
  mime: string;
  url: string;
  thumbnail_url: string | null;
  expires_in: number;
}

export interface UploadedPhoto {
  id: string;
  name: string;
  mime: string;
  url: string;
  thumbnail_url: string | null;
  is_private: boolean;
}

export interface UploadedStudentDocument {
  id: string;
  name: string;
  mime: string;
  size_bytes: number;
  url: string;
  thumbnail_url: string | null;
  is_private: boolean;
  owner_entity_type: string | null;
  owner_entity_id: string | null;
  created_at: string | null;
}

export interface DocumentList {
  items: UploadedStudentDocument[];
}

export interface PersonSearchResult {
  id: string;
  full_name: string;
  given_name_en: string | null;
  father_name_en: string | null;
  grandfather_name_en: string | null;
  date_of_birth: string | null;
}

export interface PersonSearchList {
  items: PersonSearchResult[];
  next_cursor: string | null;
}

export interface StudentFilters {
  q: string;
  status: StudentStatus | "";
  year_id: string;
  level_id: string;
  section_id: string;
}

export interface SavedView {
  id: string;
  name: string;
  filters: StudentFilters;
}
