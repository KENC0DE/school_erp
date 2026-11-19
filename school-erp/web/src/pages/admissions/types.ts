import type { CustomFieldDefinition } from "../../components/CustomFieldsForm";
import type { NameValue } from "../../components/NameFields";
import type { DuplicateWarning, Person } from "../students/types";

export type { DuplicateWarning };

export type AdmissionStatus =
  | "applied"
  | "reviewed"
  | "test"
  | "offered"
  | "accepted"
  | "enrolled"
  | "rejected"
  | "withdrawn";

export type DecisionStatus =
  | "reviewed"
  | "test"
  | "offered"
  | "accepted"
  | "rejected"
  | "withdrawn";

export type ApplicationSource = "office" | "phone" | "walk_in" | "public";

export interface AdmissionGuardian {
  id: string;
  application_id: string;
  person_id: string;
  relationship: string;
  is_primary: boolean;
  can_pickup: boolean;
  wants_account: boolean;
  account_user_id: string | null;
  notes: string | null;
  person: Person;
  row_version: number;
}

export interface ApplicationSummary {
  id: string;
  application_number: string;
  status: AdmissionStatus;
  applied_on: string | null;
  source: string;
  person: Person;
  year_id: string;
  year_code: string | null;
  year_name: string | null;
  level_id: string;
  level_code: string | null;
  level_name: string | null;
  section_id: string | null;
  section_code: string | null;
  entrance_test_score: number | null;
  student_id: string | null;
  student_number: string | null;
  row_version: number;
}

export interface ApplicationDetail extends ApplicationSummary {
  notes: string | null;
  custom: Record<string, unknown>;
  guardians: AdmissionGuardian[];
  decision_notes: string | null;
  decided_by: string | null;
  decided_at: string | null;
  converted_at: string | null;
  test_max_score: number;
  test_pass_score: number | null;
  test_passed: boolean | null;
}

export interface ApplicationList {
  items: ApplicationSummary[];
  next_cursor: string | null;
  total: number | null;
}

export interface ApplicationCreateOut extends ApplicationDetail {
  duplicate_warnings: DuplicateWarning[];
}

export interface ApplicationPreview {
  will_create: string;
  application_number: string;
  full_name: string;
  year_code: string | null;
  level_code: string | null;
  section_code: string | null;
  guardian_count: number;
  custom_field_count: number;
  duplicate_warnings: DuplicateWarning[];
}

export interface GuardianAccountPlan {
  person_id: string;
  name: string;
  email: string | null;
  action: "create" | "existing_user" | "no_email" | "role_missing";
}

export interface ConversionPreview {
  can_convert: boolean;
  reason: string | null;
  student_number: string | null;
  student_number_generated: boolean;
  year_code: string | null;
  level_code: string | null;
  section_code: string | null;
  section_source: "application" | "auto" | "none";
  guardian_count: number;
  accounts: GuardianAccountPlan[];
  warnings: string[];
}

export interface ConversionOut {
  application: ApplicationDetail;
  student_id: string;
  student_number: string;
  enrollment_id: string;
  guardian_ids: string[];
  accounts: GuardianAccountPlan[];
  warnings: string[];
}

export interface DecisionOut {
  application: ApplicationDetail;
  previous_status: AdmissionStatus;
  status: AdmissionStatus;
}

export interface AdmissionForm {
  entity_type: string;
  fields: CustomFieldDefinition[];
  entrance_test_enabled: boolean;
  entrance_test_max_score: number;
  entrance_test_pass_score: number | null;
  require_guardian: boolean;
  public_form_enabled: boolean;
}

export interface PublicOption {
  id: string;
  code: string;
  name: string;
}

export interface PublicForm {
  enabled: boolean;
  school_name: string;
  form_token: string | null;
  min_seconds: number;
  fields: CustomFieldDefinition[];
  years: PublicOption[];
  levels: PublicOption[];
  entrance_test_enabled: boolean;
  entrance_test_max_score: number;
  entrance_test_pass_score: number | null;
  require_guardian: boolean;
}

export interface PublicApplicationResult {
  application_number: string;
  full_name: string;
  status: "applied";
  year_code: string | null;
  level_code: string | null;
}

export interface ApplicationDocument {
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

export interface ApplicationDocumentList {
  items: ApplicationDocument[];
}

export interface ApplicationFilters {
  q: string;
  status: AdmissionStatus | "";
  year_id: string;
  level_id: string;
}

export interface GuardianDraft {
  uid: string;
  relationship: string;
  is_primary: boolean;
  can_pickup: boolean;
  wants_account: boolean;
  names: NameValue;
  phone: string;
  email: string;
}
