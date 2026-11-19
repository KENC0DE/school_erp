import type {
  Layout,
  LayoutElement,
  TableElement,
  TextElement,
  TextStyle,
} from "@erp/documents";

import type { FieldDefinition } from "../types";
import { pageSizeMm } from "../types";

let sequence = 0;

export function newId(prefix = "el"): string {
  sequence += 1;
  return `${prefix}_${Date.now().toString(36)}_${sequence.toString(36)}`;
}

export const DEFAULT_TEXT_STYLE: TextStyle = {
  font_family: "Inter",
  font_size_pt: 12,
  bold: false,
  italic: false,
  underline: false,
  colour: "#111111",
  line_height: 1.2,
  letter_spacing_pt: 0,
};

function base(layout: Layout, width: number, height: number) {
  const margin = layout.page.margins_mm;
  return {
    id: newId(),
    rect: {
      x_mm: margin.left,
      y_mm: margin.top,
      w_mm: width,
      h_mm: height,
    },
    z: nextZ(layout),
    rotation_deg: 0,
    locked: false,
  };
}

export function nextZ(layout: Layout): number {
  return (layout.elements.reduce((max, element) => Math.max(max, element.z), 0) || 0) + 1;
}

export function newText(layout: Layout, contentKey = "New text"): TextElement {
  return {
    ...base(layout, 80, 14),
    type: "text",
    content: contentKey,
    style: { ...DEFAULT_TEXT_STYLE },
    align: "left",
    vertical_align: "top",
    wrap: true,
  };
}

export function newFieldText(layout: Layout, fieldKey: string): TextElement {
  const element = newText(layout, `{{${fieldKey}}}`);
  element.rect.w_mm = 70;
  element.rect.h_mm = 10;
  return element;
}

export function newImage(
  layout: Layout,
  source: { kind: "field" | "file" | "url"; value: string } = { kind: "url", value: "" },
): LayoutElement {
  return {
    ...base(layout, 40, 30),
    type: "image",
    source,
    fit: "contain",
  };
}

export function newShape(layout: Layout, shape: "rect" | "ellipse" | "line" = "rect"): LayoutElement {
  return {
    ...base(layout, shape === "line" ? 60 : 40, shape === "line" ? 0.5 : 20),
    type: "shape",
    shape,
    fill: shape === "line" ? undefined : "#e5e7eb",
    stroke: { colour: "#334155", width_mm: shape === "line" ? 0.4 : 0 },
    radius_mm: 0,
  };
}

export function newTable(layout: Layout): TableElement {
  return {
    ...base(layout, 170, 40),
    type: "table",
    table: {
      source: "student.marks.subjects",
      show_header: true,
      repeat_header: true,
      row_height_mm: 7,
      columns: [
        { key: "subject", label: "Subject", binding: "subject", width_mm: 70, align: "left" },
        { key: "total", label: "Total", binding: "total", width_mm: 30, align: "right" },
        { key: "grade", label: "Grade", binding: "grade", width_mm: 30, align: "center" },
      ],
      summaries: [],
    },
    style: { ...DEFAULT_TEXT_STYLE, font_size_pt: 9 },
  };
}

export function newQr(layout: Layout, data = "https://demo.school/verify/SN-0001"): LayoutElement {
  return {
    ...base(layout, 24, 24),
    type: "qr",
    data,
    error_correction: "M",
    foreground: "#000000",
    background: "#ffffff",
  };
}

export function newBarcode(layout: Layout, data = "DEMO-2026-0001"): LayoutElement {
  return {
    ...base(layout, 50, 18),
    type: "barcode",
    data,
    symbology: "code128",
    show_text: true,
    foreground: "#000000",
    background: "#ffffff",
  };
}

export const PLACEHOLDER_SOURCES: Record<
  "logo" | "signature" | "stamp" | "photo",
  { kind: "field"; value: string }
> = {
  logo: { kind: "field", value: "school.logo" },
  signature: { kind: "field", value: "student.signature" },
  stamp: { kind: "field", value: "school.stamp" },
  photo: { kind: "field", value: "student.photo" },
};

const TOKEN = /\{\{\s*([A-Za-z0-9_.-]+)\s*(?:\|\s*([A-Za-z]+)\s*)?\}\}/g;

export function sampleFor(field: FieldDefinition | undefined): string {
  if (!field || field.sample === null || field.sample === undefined) return "—";
  if (Array.isArray(field.sample) || typeof field.sample === "object") return field.key;
  return String(field.sample);
}

/** Replace every `{{field}}` token with that field's registered sample. */
export function resolveSample(
  content: string,
  fields: Map<string, FieldDefinition>,
): string {
  return content.replace(TOKEN, (match, key: string) => {
    const field = fields.get(key);
    return field ? sampleFor(field) : match;
  });
}

/** The token a palette click inserts, including the requested forms. */
export function tokenFor(field: FieldDefinition, format?: "ec" | "gc" | "am" | "en"): string {
  return `{{${field.key}${format ? `|${format}` : ""}}}`;
}

export function insertToken(content: string, token: string): string {
  if (!content.trim()) return token;
  return `${content}${/\s$/.test(content) ? "" : " "}${token}`;
}

export function countTokens(content: string): number {
  return Array.from(content.matchAll(TOKEN)).length;
}

export function elementLabelKey(element: LayoutElement): string {
  return `editor.add_${element.type === "shape" ? element.shape : element.type}`;
}

/** Keep an element inside the page while dragging. */
export function clampToPage(layout: Layout, rect: LayoutElement["rect"]): LayoutElement["rect"] {
  const page = pageSizeMm(layout.page);
  const width = Math.min(rect.w_mm, page.width);
  const height = Math.min(rect.h_mm, page.height);
  return {
    x_mm: Math.max(0, Math.min(rect.x_mm, Math.max(0, page.width - width))),
    y_mm: Math.max(0, Math.min(rect.y_mm, Math.max(0, page.height - height))),
    w_mm: width,
    h_mm: height,
  };
}
