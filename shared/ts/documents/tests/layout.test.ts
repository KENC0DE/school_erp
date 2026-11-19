/**
 * P5-01: the version 1 document layout schema.
 *
 * Both this suite and `school-erp/backend/tests/test_document_layout.py`
 * validate the same fixture corpus, so the Zod definition, the generated JSON
 * Schema and the Pydantic models cannot drift apart.
 */

import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  LAYOUT_SCHEMA_ID,
  LAYOUT_SCHEMA_VERSION,
  LayoutSchema,
  safeValidateLayout,
  validateLayout,
} from "../src/layout";
import { renderJsonSchema } from "../scripts/gen-schema.ts";

interface Fixture {
  name: string;
  layout: unknown;
}

interface Corpus {
  valid: Fixture[];
  invalid: Fixture[];
}

const HERE = new URL(".", import.meta.url);
const corpus = JSON.parse(
  readFileSync(new URL("../../../schema/document-layout.fixtures.json", HERE), "utf8"),
) as Corpus;

const committedSchema = readFileSync(
  new URL("../../../schema/document-layout.v1.json", HERE),
  "utf8",
);

/** Walk plain JSON and compare only the keys the fixture actually declares. */
function expectSubset(actual: unknown, expected: unknown, path = "$"): void {
  if (Array.isArray(expected)) {
    expect(Array.isArray(actual), `${path} should be an array`).toBe(true);
    expect((actual as unknown[]).length, `${path} length`).toBe(expected.length);
    expected.forEach((item, index) =>
      expectSubset((actual as unknown[])[index], item, `${path}[${index}]`),
    );
    return;
  }
  if (expected !== null && typeof expected === "object") {
    expect(actual !== null && typeof actual === "object", `${path} should be an object`).toBe(
      true,
    );
    for (const [key, value] of Object.entries(expected)) {
      expectSubset((actual as Record<string, unknown>)[key], value, `${path}.${key}`);
    }
    return;
  }
  expect(actual, `${path} value`).toEqual(expected);
}

describe("layout schema", () => {
  it("pins the version and schema id", () => {
    expect(LAYOUT_SCHEMA_VERSION).toBe(1);
    expect(LAYOUT_SCHEMA_ID).toBe("https://erp.local/schema/document-layout.v1.json");
  });

  it("has a corpus with both outcomes", () => {
    expect(corpus.valid.length).toBeGreaterThanOrEqual(4);
    expect(corpus.invalid.length).toBeGreaterThanOrEqual(15);
  });

  describe("valid fixtures", () => {
    for (const fixture of corpus.valid) {
      it(`accepts ${fixture.name} and round-trips it`, () => {
        const parsed = validateLayout(fixture.layout);
        // Nothing the author sent may change through validation.
        expectSubset(parsed, fixture.layout);
        // Dumping and re-parsing is stable (defaults do not drift).
        const again = validateLayout(JSON.parse(JSON.stringify(parsed)));
        expect(again).toEqual(parsed);
      });
    }
  });

  describe("invalid fixtures", () => {
    for (const fixture of corpus.invalid) {
      it(`rejects ${fixture.name}`, () => {
        const result = safeValidateLayout(fixture.layout);
        expect(result.success).toBe(false);
        expect(() => validateLayout(fixture.layout)).toThrow();
      });
    }
  });

  it("applies the documented defaults", () => {
    const layout = validateLayout({ version: 1, page: { size: "A4" } });
    expect(layout.page.orientation).toBe("portrait");
    expect(layout.page.margins_mm).toEqual({ top: 12, right: 12, bottom: 12, left: 12 });
    expect(layout.page.bleed_mm).toBe(0);
    expect(layout.fonts).toEqual([]);
    expect(layout.elements).toEqual([]);
  });

  it("defaults a text element to a readable style", () => {
    const layout = validateLayout({
      version: 1,
      page: { size: "A4" },
      elements: [
        {
          id: "note",
          type: "text",
          rect: { x_mm: 10, y_mm: 20, w_mm: 100, h_mm: 10 },
          content: "Hello",
          style: { font_family: "Inter", font_size_pt: 12 },
        },
      ],
    });
    const element = layout.elements[0];
    expect(element.type).toBe("text");
    if (element.type !== "text") throw new Error("unreachable");
    expect(element.style.bold).toBe(false);
    expect(element.style.colour).toBe("#111111");
    expect(element.style.line_height).toBe(1.2);
    expect(element.align).toBe("left");
    expect(element.vertical_align).toBe("top");
    expect(element.locked).toBe(false);
    expect(element.z).toBe(0);
  });

  it("reports duplicate ids at the offending element", () => {
    const result = safeValidateLayout({
      version: 1,
      page: { size: "A4" },
      elements: [
        {
          id: "dup",
          type: "shape",
          rect: { x_mm: 0, y_mm: 0, w_mm: 10, h_mm: 10 },
          shape: "rect",
        },
        {
          id: "dup",
          type: "shape",
          rect: { x_mm: 20, y_mm: 0, w_mm: 10, h_mm: 10 },
          shape: "rect",
        },
      ],
    });
    expect(result.success).toBe(false);
    if (result.success) return;
    expect(result.error.issues.map((issue) => issue.message)).toContain(
      'duplicate element id "dup"',
    );
  });
});

describe("generated JSON Schema", () => {
  it("matches the committed artifact", () => {
    expect(committedSchema).toBe(renderJsonSchema());
  });

  it("describes the version, page and element union", () => {
    const schema = JSON.parse(committedSchema) as Record<string, any>;
    expect(schema.$id).toBe(LAYOUT_SCHEMA_ID);
    expect(schema.required).toEqual(expect.arrayContaining(["version", "page"]));
    expect(schema.properties.version.const).toBe(1);
    expect(schema.properties.page.properties.size.enum).toEqual([
      "A4",
      "A5",
      "Letter",
      "custom",
    ]);
    const elementTypes = schema.properties.elements.items.oneOf.map(
      (entry: { properties: { type: { const: string } } }) => entry.properties.type.const,
    );
    expect(elementTypes.sort()).toEqual(
      ["barcode", "image", "qr", "shape", "table", "text"].sort(),
    );
  });

  it("keeps every object closed", () => {
    const schema = JSON.parse(committedSchema) as Record<string, any>;
    expect(schema.additionalProperties).toBe(false);
    const elementTypes = schema.properties.elements.items.oneOf as Record<string, any>[];
    for (const entry of elementTypes) {
      expect(entry.additionalProperties).toBe(false);
    }
  });
});
