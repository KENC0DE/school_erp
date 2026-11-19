import type { Layout } from "@erp/documents";

export type DocType =
  | "report_card"
  | "transcript"
  | "certificate_completion"
  | "certificate_appreciation"
  | "id_card"
  | "admission_letter"
  | "receipt"
  | "invoice"
  | "experience_letter"
  | "custom";

export const DOC_TYPES: DocType[] = [
  "report_card",
  "transcript",
  "certificate_completion",
  "certificate_appreciation",
  "id_card",
  "admission_letter",
  "receipt",
  "invoice",
  "experience_letter",
  "custom",
];

export interface VersionSummary {
  id: string;
  version_number: number;
  status: "draft" | "published";
  change_note: string | null;
  published_at: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
}

export interface VersionDetail extends VersionSummary {
  template_id: string;
  layout: Layout;
}

export interface TemplateSummary {
  id: string;
  key: string;
  name: string;
  description: string | null;
  doc_type: DocType;
  row_version: number;
  current_version_id: string | null;
  current_version_number: number | null;
  draft_version_id: string | null;
  draft_version_number: number | null;
  version_count: number;
  updated_at: string;
}

export interface TemplateDetail extends TemplateSummary {
  versions: VersionSummary[];
}

export interface TemplateList {
  items: TemplateSummary[];
  total: number;
}

export interface FieldDefinition {
  key: string;
  label_key: string;
  kind: "text" | "integer" | "decimal" | "date" | "boolean" | "table";
  formats: string[];
  sample: unknown;
  module: string;
}

export interface FieldsResponse {
  items: FieldDefinition[];
  format_options: {
    calendar: string[];
    script: string[];
    money: string[];
  };
}

export interface PreviewResponse {
  mode: "sample" | "student";
  html: string;
  page_mm: [number, number];
  media_mm: [number, number];
  student_id: string | null;
  student_name: string | null;
}

export interface StudentOption {
  id: string;
  student_number: string;
  status: string;
  person: {
    full_name: string;
  };
  enrollment: {
    level_name: string | null;
    section_code: string | null;
  } | null;
}

export interface StudentList {
  items: StudentOption[];
  next_cursor: string | null;
  total: number;
}

export interface Starter {
  key: string;
  doc_type: DocType;
  name_key: string;
  description_key: string;
  layout: Layout;
}

export interface StarterList {
  items: Starter[];
}

export interface TemplateFile {
  format: "school-erp.doc-template";
  format_version: 1;
  exported_at: string | null;
  template: {
    key: string;
    name: string;
    description: string | null;
    doc_type: DocType;
  };
  versions: Array<{
    version_number: number;
    status: "draft" | "published";
    change_note: string | null;
    published_at: string | null;
    layout: Layout;
  }>;
}

export const PAGE_PRESETS: Record<"A4" | "A5" | "Letter", { width: number; height: number }> = {
  A4: { width: 210, height: 297 },
  A5: { width: 148, height: 210 },
  Letter: { width: 215.9, height: 279.4 },
};

/** Trim size in millimetres, with the orientation applied. */
export function pageSizeMm(page: Layout["page"]): { width: number; height: number } {
  const preset =
    page.size === "custom"
      ? { width: page.width_mm ?? 210, height: page.height_mm ?? 297 }
      : PAGE_PRESETS[page.size];
  return page.orientation === "landscape"
    ? { width: preset.height, height: preset.width }
    : { width: preset.width, height: preset.height };
}

export function isDraft(template: TemplateDetail | TemplateSummary): boolean {
  return Boolean(template.draft_version_id);
}

export interface GenerationYear {
  id: string;
  code: string;
  name: string;
  is_current: boolean;
}

export interface GenerationLevel {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
}

export interface GenerationSection {
  id: string;
  year_id: string;
  level_id: string;
  code: string;
  name: string | null;
}

export interface GenerationTargets {
  year: GenerationYear | null;
  levels: GenerationLevel[];
  sections: GenerationSection[];
}

export interface GenerationStudent {
  id: string;
  student_number: string;
  full_name: string;
  level_name: string | null;
  section_code: string | null;
}

export interface GenerationStudentList {
  items: GenerationStudent[];
}

export interface GenerationStaff {
  id: string;
  staff_number: string;
  full_name: string;
  position_name: string | null;
  department_name: string | null;
}

export interface GenerationStaffList {
  items: GenerationStaff[];
}

export type GenerationTargetType = "student" | "staff" | "section" | "level";

export interface GenerationRequest {
  template_id: string;
  version_id?: string | null;
  combine: boolean;
  target:
    | { type: "student"; student_id: string; year_id?: string | null }
    | { type: "staff"; staff_id: string }
    | { type: "section"; section_id: string; year_id?: string | null }
    | { type: "level"; level_id: string; year_id?: string | null };
}

export interface GenerationStarted {
  job_id: string;
  batch_id: string;
  count: number;
  status: string;
}

export interface GenerationBatch {
  id: string;
  template_id: string;
  template_name: string;
  template_version_id: string;
  template_version_number: number;
  mode: GenerationTargetType;
  combine: boolean;
  count: number;
  issued_count: number;
  failed_count: number;
  progress: number;
  status:
    | "pending_approval"
    | "queued"
    | "running"
    | "succeeded"
    | "failed"
    | "cancelled"
    | "rejected";
  approval_required: boolean;
  requested_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  file_id: string | null;
  download_url: string | null;
  failure_summary: string | null;
  created_at: string;
  issued_at: string | null;
}

export interface GenerationBatchList {
  items: GenerationBatch[];
}

export interface IssuedDocument {
  id: string;
  number: string;
  verification_code: string;
  template_id: string;
  template_name: string;
  doc_type: DocType;
  template_version_number: number;
  recipient_type: string;
  recipient_id: string | null;
  recipient_name: string;
  batch_id: string | null;
  file_id: string | null;
  download_url: string | null;
  issued_at: string;
}

export interface IssuedDocumentList {
  items: IssuedDocument[];
  next_cursor: string | null;
  total: number | null;
}

export interface DocumentVerification {
  valid: boolean;
  number: string;
  doc_type: DocType;
  recipient_name: string;
  issued_at: string;
  school_name: string | null;
}

export interface FileLink {
  file_id: string | null;
  filename: string | null;
  url: string | null;
  checksum_sha256: string | null;
}

export interface ReprintResult {
  id: string;
  number: string;
  file_id: string | null;
  url: string | null;
  checksum_sha256: string | null;
}
