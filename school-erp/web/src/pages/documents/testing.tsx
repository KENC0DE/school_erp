import type { Layout } from "@erp/documents";
import { QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import coreEn from "../../../../backend/core/i18n/en.json";
import documentsEn from "../../../../backend/modules/documents/i18n/en.json";
import studentsEn from "../../../../backend/modules/students/i18n/en.json";
import { AppProviders, AppRoutes } from "../../App";
import type { FieldDefinition, TemplateDetail, VersionDetail } from "./types";

function prefix(prefix: string, bundle: Record<string, string>) {
  return Object.fromEntries(Object.entries(bundle).map(([key, value]) => [`${prefix}.${key}`, value]));
}

export const documentMessages: Record<string, string> = {
  ...coreEn,
  ...prefix("documents", documentsEn),
  ...prefix("students", studentsEn),
};

export interface MockRequest {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function session(permissions: string[] = ["*"], roles: string[] = ["super_admin"]) {
  return {
    id: "u-1",
    email: "superadmin@demo.school",
    display_name: "Super Admin",
    locale: "en",
    roles,
    permissions,
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [
      {
        key: "documents",
        label_key: "documents.nav",
        path: "/documents",
        module: "documents",
      },
    ],
    modules: ["documents"],
    locale: "en",
    languages: ["en", "am"],
  };
}

export function stubDocuments(
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

export function renderDocuments(path = "/documents") {
  return render(
    <AppProviders
      initialMessages={documentMessages}
      queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

export const LAYOUT: Layout = {
  version: 1,
  page: {
    size: "A4",
    orientation: "landscape",
    margins_mm: { top: 12, right: 12, bottom: 12, left: 12 },
    bleed_mm: 0,
  },
  fonts: [],
  elements: [],
};

export const FIELDS: FieldDefinition[] = [
  {
    key: "student.full_name",
    label_key: "students.field.full_name",
    kind: "text",
    formats: ["script"],
    sample: "Abebe Kebede Tadesse",
    module: "students",
  },
  {
    key: "student.student_number",
    label_key: "students.field.student_number",
    kind: "text",
    formats: [],
    sample: "DEMO-2026-0001",
    module: "students",
  },
  {
    key: "student.marks.subjects",
    label_key: "assessment.field.marks_subjects",
    kind: "table",
    formats: [],
    sample: [
      {
        subject: "Mathematics",
        total: "35.69",
        grade: "C+",
      },
    ],
    module: "assessment",
  },
];

export function fieldsResponse() {
  return {
    items: FIELDS,
    format_options: { calendar: ["ec", "gc", "both"], script: ["am", "en"], money: ["etb"] },
  };
}

export function template(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    id: "tpl-1",
    key: "certificate-completion",
    name: "Certificate of completion",
    description: null,
    doc_type: "certificate_completion",
    row_version: 1,
    current_version_id: "ver-1",
    current_version_number: 1,
    draft_version_id: "ver-1",
    draft_version_number: 1,
    version_count: 1,
    updated_at: "2026-11-19T09:00:00Z",
    versions: [
      {
        id: "ver-1",
        version_number: 1,
        status: "draft",
        change_note: null,
        published_at: null,
        row_version: 1,
        created_at: "2026-11-19T09:00:00Z",
        updated_at: "2026-11-19T09:00:00Z",
      },
    ],
    ...overrides,
  };
}

export function version(overrides: Partial<VersionDetail> = {}): VersionDetail {
  return {
    id: "ver-1",
    template_id: "tpl-1",
    version_number: 1,
    status: "draft",
    change_note: null,
    published_at: null,
    row_version: 1,
    created_at: "2026-11-19T09:00:00Z",
    updated_at: "2026-11-19T09:00:00Z",
    layout: LAYOUT,
    ...overrides,
  };
}

export function starters() {
  return {
    items: [
      {
        key: "certificate_completion",
        doc_type: "certificate_completion",
        name_key: "documents.starter.certificate_completion.name",
        description_key: "documents.starter.certificate_completion.description",
        layout: LAYOUT,
      },
      {
        key: "id_card",
        doc_type: "id_card",
        name_key: "documents.starter.id_card.name",
        description_key: "documents.starter.id_card.description",
        layout: LAYOUT,
      },
    ],
  };
}

export function generationTargets() {
  return {
    year: { id: "year-1", code: "2026-2027", name: "2026/27", is_current: true },
    levels: [{ id: "lvl-5", code: "g5", name: "Grade 5", name_am: "5ኛ ክፍል" }],
    sections: [
      { id: "sec-a", year_id: "year-1", level_id: "lvl-5", code: "A", name: null },
    ],
  };
}

export function generationStudents() {
  return {
    items: [
      {
        id: "stu-1",
        student_number: "STU-2026-0001",
        full_name: "Abebe Dawit Samuel",
        level_name: "Grade 5",
        section_code: "A",
      },
    ],
  };
}

export function generationStaff() {
  return {
    items: [
      {
        id: "staff-1",
        staff_number: "STF-2026-0001",
        full_name: "Solomon Tesfaye Gebre",
        position_name: "Mathematics Teacher",
        department_name: "Science",
      },
    ],
  };
}

export function generationBatch(overrides: Record<string, unknown> = {}) {
  return {
    id: "batch-1",
    template_id: "tpl-1",
    template_name: "Certificate of completion",
    template_version_id: "ver-1",
    template_version_number: 1,
    mode: "student",
    combine: false,
    count: 1,
    issued_count: 1,
    failed_count: 0,
    progress: 100,
    status: "succeeded",
    approval_required: false,
    requested_by: "Super Admin",
    approved_at: null,
    rejection_reason: null,
    file_id: null,
    download_url: null,
    failure_summary: null,
    created_at: "2026-11-19T09:00:00Z",
    issued_at: "2026-11-19T09:01:00Z",
    ...overrides,
  };
}

export function issuedDocument(overrides: Record<string, unknown> = {}) {
  return {
    id: "issued-1",
    number: "DOC-2026-00001",
    verification_code: "abc123def456",
    template_id: "tpl-1",
    template_name: "Certificate of completion",
    doc_type: "certificate_completion",
    template_version_number: 1,
    recipient_type: "student",
    recipient_id: "stu-1",
    recipient_name: "Abebe Dawit Samuel",
    batch_id: "batch-1",
    file_id: "file-1",
    download_url: "http://localhost/files/doc.pdf",
    issued_at: "2026-11-19T09:01:00Z",
    ...overrides,
  };
}

export function issuedList(items = [issuedDocument()]) {
  return { items, next_cursor: null, total: items.length };
}
