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
