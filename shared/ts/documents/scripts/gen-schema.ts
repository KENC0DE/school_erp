/**
 * Export the layout schema as committed JSON Schema (P5-01).
 *
 *   node scripts/gen-schema.ts           # check the committed artifact
 *   node scripts/gen-schema.ts --write   # regenerate it
 *
 * The backend's Pydantic models and this artifact are checked against each
 * other, so a change to `src/layout.ts` without a regenerated JSON file fails
 * the test suites rather than drifting silently.
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { z } from "zod";

import { LAYOUT_SCHEMA_ID, LayoutSchema } from "../src/layout.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, "../../../schema/document-layout.v1.json");

export function buildJsonSchema(): Record<string, unknown> {
  return z.toJSONSchema(LayoutSchema, {
    target: "draft-2020-12",
    io: "input",
    unrepresentable: "any",
  }) as Record<string, unknown>;
}

export function renderJsonSchema(): string {
  const schema = {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    $id: LAYOUT_SCHEMA_ID,
    title: "Document layout",
    description:
      "Versioned Document Studio layout. Geometry is millimetres. Generated from shared/ts/documents/src/layout.ts.",
    ...buildJsonSchema(),
  };
  // Two-space indent and a trailing newline so the file is prettier-stable.
  return `${JSON.stringify(schema, null, 2)}\n`;
}

function main(argv: string[]): number {
  const write = argv.includes("--write");
  const expected = renderJsonSchema();
  if (write) {
    mkdirSync(dirname(OUT), { recursive: true });
    writeFileSync(OUT, expected);
    console.log(`gen-schema: wrote ${OUT}`);
    return 0;
  }
  let actual: string;
  try {
    actual = readFileSync(OUT, "utf8");
  } catch {
    console.error(`gen-schema: ${OUT} is missing; run with --write`);
    return 1;
  }
  if (actual !== expected) {
    console.error(`gen-schema: ${OUT} is stale; run with --write`);
    return 1;
  }
  console.log("gen-schema: document layout schema is up to date");
  return 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.exitCode = main(process.argv.slice(2));
}
