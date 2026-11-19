/**
 * Document layout schema, version 1 (P5-01).
 *
 * One Zod definition is the authoring source for the canvas editor, the
 * renderer and the backend. `scripts/gen-schema.ts` exports it as
 * `shared/schema/document-layout.v1.json`, the committed artifact the Python
 * models are checked against, and both test suites validate the same shared
 * fixture corpus (`shared/schema/document-layout.fixtures.json`).
 *
 * Geometry is millimetres as JSON numbers. Positions and sizes are layout
 * data, not money or marks, so exact decimal arithmetic is unnecessary; the
 * renderer multiplies them by the page scale once.
 *
 * Refinements that JSON Schema cannot express (unique element ids, the custom
 * page-size rule, unique table column keys) are enforced by `superRefine` here
 * and by matching validators in `core/documents/layout.py`.
 */

import { z } from "zod";

export const LAYOUT_SCHEMA_VERSION = 1 as const;

export const LAYOUT_SCHEMA_ID =
  "https://erp.local/schema/document-layout.v1.json" as const;

const IDENTIFIER = /^[a-zA-Z0-9][a-zA-Z0-9_-]*$/;
const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;

const identifierSchema = z.string().min(1).max(64).regex(IDENTIFIER);
const colourSchema = z.string().regex(HEX_COLOR);
const lengthSchema = z.number().min(0).max(5000);
const positiveLengthSchema = z.number().gt(0).max(5000);

export const RectSchema = z.strictObject({
  x_mm: lengthSchema,
  y_mm: lengthSchema,
  w_mm: positiveLengthSchema,
  h_mm: positiveLengthSchema,
});

export const FormatOptionsSchema = z.strictObject({
  calendar: z.enum(["ec", "gc", "both"]).optional(),
  script: z.enum(["am", "en", "both"]).optional(),
  money: z.literal("etb").optional(),
  date_pattern: z.string().min(1).max(40).optional(),
  number_decimals: z.number().int().min(0).max(6).optional(),
});

export const TextStyleSchema = z.strictObject({
  font_family: z.string().min(1).max(100),
  font_size_pt: z.number().min(4).max(200),
  bold: z.boolean().default(false),
  italic: z.boolean().default(false),
  underline: z.boolean().default(false),
  colour: colourSchema.default("#111111"),
  line_height: z.number().min(0.5).max(4).default(1.2),
  letter_spacing_pt: z.number().min(-2).max(10).default(0),
});

/** A comparison against one bound field. */
export const ConditionLeafSchema = z.strictObject({
  op: z.enum(["eq", "ne", "gt", "gte", "lt", "lte", "contains"]),
  field: z.string().min(1).max(120),
  value: z.union([z.string().max(500), z.number(), z.boolean()]),
});

/** A presence check against one bound field. */
export const ConditionPresenceSchema = z.strictObject({
  op: z.enum(["exists", "empty"]),
  field: z.string().min(1).max(120),
});

export type Condition =
  | z.infer<typeof ConditionLeafSchema>
  | z.infer<typeof ConditionPresenceSchema>
  | { all: Condition[] }
  | { any: Condition[] };

export const ConditionSchema: z.ZodType<Condition> = z.lazy(() =>
  z.union([
    ConditionLeafSchema,
    ConditionPresenceSchema,
    z.strictObject({ all: z.array(ConditionSchema).min(1).max(20) }),
    z.strictObject({ any: z.array(ConditionSchema).min(1).max(20) }),
  ]),
);

export const TableColumnSchema = z.strictObject({
  key: identifierSchema,
  label: z.string().min(1).max(120),
  // The field this column reads from one repeating row. Omitted for a static
  // column (a number column, a blank spacer, ...).
  binding: z.string().min(1).max(120).optional(),
  width_mm: z.number().gt(0).max(2000).optional(),
  align: z.enum(["left", "center", "right"]).default("left"),
  format: FormatOptionsSchema.optional(),
});

export const TableSummarySchema = z.strictObject({
  column: identifierSchema,
  aggregate: z.enum(["sum", "average", "count"]),
  label: z.string().min(1).max(120),
});

export const TableSpecSchema = z
  .strictObject({
    // A repeating field, e.g. `student.marks.subjects`.
    source: z.string().min(1).max(120),
    show_header: z.boolean().default(true),
    repeat_header: z.boolean().default(true),
    row_height_mm: z.number().min(3).max(50).default(6),
    columns: z.array(TableColumnSchema).min(1).max(30),
    summaries: z.array(TableSummarySchema).max(10).default([]),
  })
  .superRefine((table, ctx) => {
    const seen = new Set<string>();
    table.columns.forEach((column, index) => {
      if (seen.has(column.key)) {
        ctx.addIssue({
          code: "custom",
          message: `duplicate table column "${column.key}"`,
          path: ["columns", index, "key"],
        });
      }
      seen.add(column.key);
    });
    table.summaries.forEach((summary, index) => {
      if (!seen.has(summary.column)) {
        ctx.addIssue({
          code: "custom",
          message: `summary names unknown column "${summary.column}"`,
          path: ["summaries", index, "column"],
        });
      }
    });
  });

export const ImageSourceSchema = z.strictObject({
  kind: z.enum(["field", "file", "url"]),
  value: z.string().min(1).max(500),
});

export const StrokeSchema = z.strictObject({
  colour: colourSchema,
  width_mm: z.number().min(0).max(20),
});

const baseElementShape = {
  id: identifierSchema,
  rect: RectSchema,
  z: z.number().int().min(-1000).max(1000).default(0),
  rotation_deg: z.number().min(-180).max(180).default(0),
  visible_when: ConditionSchema.optional(),
  locked: z.boolean().default(false),
};

export const TextElementSchema = z.strictObject({
  ...baseElementShape,
  type: z.literal("text"),
  // Literal text with optional `{{field}}` tokens.
  content: z.string().min(1).max(4000),
  style: TextStyleSchema,
  align: z.enum(["left", "center", "right"]).default("left"),
  vertical_align: z.enum(["top", "middle", "bottom"]).default("top"),
  wrap: z.boolean().default(true),
  format: FormatOptionsSchema.optional(),
});

export const ImageElementSchema = z.strictObject({
  ...baseElementShape,
  type: z.literal("image"),
  source: ImageSourceSchema,
  fit: z.enum(["contain", "cover", "fill"]).default("contain"),
  alt: z.string().min(1).max(200).optional(),
});

export const ShapeElementSchema = z.strictObject({
  ...baseElementShape,
  type: z.literal("shape"),
  shape: z.enum(["rect", "ellipse", "line"]),
  fill: colourSchema.optional(),
  stroke: StrokeSchema.optional(),
  radius_mm: z.number().min(0).max(100).default(0),
});

export const TableElementSchema = z.strictObject({
  ...baseElementShape,
  type: z.literal("table"),
  table: TableSpecSchema,
  style: TextStyleSchema,
});

export const QrElementSchema = z.strictObject({
  ...baseElementShape,
  type: z.literal("qr"),
  data: z.string().min(1).max(500),
  error_correction: z.enum(["L", "M", "Q", "H"]).default("M"),
  foreground: colourSchema.default("#000000"),
  background: colourSchema.default("#ffffff"),
});

export const BarcodeElementSchema = z.strictObject({
  ...baseElementShape,
  type: z.literal("barcode"),
  data: z.string().min(1).max(500),
  symbology: z.enum(["code128", "code39", "ean13", "ean8"]).default("code128"),
  show_text: z.boolean().default(true),
  foreground: colourSchema.default("#000000"),
  background: colourSchema.default("#ffffff"),
});

export const ElementSchema = z.discriminatedUnion("type", [
  TextElementSchema,
  ImageElementSchema,
  ShapeElementSchema,
  TableElementSchema,
  QrElementSchema,
  BarcodeElementSchema,
]);

export const MarginSchema = z.strictObject({
  top: z.number().min(0).max(100).default(12),
  right: z.number().min(0).max(100).default(12),
  bottom: z.number().min(0).max(100).default(12),
  left: z.number().min(0).max(100).default(12),
});

export const PageSchema = z
  .strictObject({
    size: z.enum(["A4", "A5", "Letter", "custom"]),
    // Only a custom page carries explicit dimensions.
    width_mm: positiveLengthSchema.optional(),
    height_mm: positiveLengthSchema.optional(),
    orientation: z.enum(["portrait", "landscape"]).default("portrait"),
    margins_mm: MarginSchema.default({
      top: 12,
      right: 12,
      bottom: 12,
      left: 12,
    }),
    bleed_mm: z.number().min(0).max(20).default(0),
    background_colour: colourSchema.optional(),
  })
  .superRefine((page, ctx) => {
    if (page.size === "custom") {
      if (page.width_mm === undefined || page.height_mm === undefined) {
        ctx.addIssue({
          code: "custom",
          message: "a custom page needs width_mm and height_mm",
          path: ["size"],
        });
      }
    } else if (page.width_mm !== undefined || page.height_mm !== undefined) {
      ctx.addIssue({
        code: "custom",
        message: "a preset page takes its dimensions from the preset",
        path: ["size"],
      });
    }
  });

export const FontSchema = z.strictObject({
  family: z.string().min(1).max(100),
  // Uploaded font file; omitted for a bundled family.
  file_id: z.string().uuid().optional(),
  fallback: z.string().min(1).max(100).optional(),
});

export const LayoutSchema = z
  .strictObject({
    version: z.literal(LAYOUT_SCHEMA_VERSION),
    name: z.string().min(1).max(120).optional(),
    page: PageSchema,
    fonts: z.array(FontSchema).max(10).default([]),
    elements: z.array(ElementSchema).max(500).default([]),
  })
  .superRefine((layout, ctx) => {
    const seen = new Set<string>();
    layout.elements.forEach((element, index) => {
      if (seen.has(element.id)) {
        ctx.addIssue({
          code: "custom",
          message: `duplicate element id "${element.id}"`,
          path: ["elements", index, "id"],
        });
      }
      seen.add(element.id);
    });
  });

export type Layout = z.infer<typeof LayoutSchema>;
export type LayoutElement = z.infer<typeof ElementSchema>;
export type TextElement = z.infer<typeof TextElementSchema>;
export type ImageElement = z.infer<typeof ImageElementSchema>;
export type ShapeElement = z.infer<typeof ShapeElementSchema>;
export type TableElement = z.infer<typeof TableElementSchema>;
export type QrElement = z.infer<typeof QrElementSchema>;
export type BarcodeElement = z.infer<typeof BarcodeElementSchema>;
export type Page = z.infer<typeof PageSchema>;
export type TableSpec = z.infer<typeof TableSpecSchema>;
export type FormatOptions = z.infer<typeof FormatOptionsSchema>;
export type TextStyle = z.infer<typeof TextStyleSchema>;

/** Parse a layout, rejecting anything the schema does not describe. */
export function validateLayout(value: unknown): Layout {
  return LayoutSchema.parse(value);
}

/** Non-throwing variant for previews and import dialogs. */
export function safeValidateLayout(value: unknown) {
  return LayoutSchema.safeParse(value);
}
