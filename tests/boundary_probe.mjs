// Lints a fixture as if it lived at a given path inside the repo, without
// writing the fixture into the working tree. Used by tests/test_zone_boundaries.py
// to prove the TypeScript zone rules actually reject cross-zone imports.
import { readFileSync } from "node:fs";
import path from "node:path";

import { ESLint } from "eslint";

const [, , fixture, target] = process.argv;
if (!fixture || !target) {
  console.error("usage: node boundary_probe.mjs <fixture> <target-path>");
  process.exit(2);
}

const eslint = new ESLint({ cwd: process.cwd() });
const [result] = await eslint.lintText(readFileSync(fixture, "utf8"), {
  filePath: path.resolve(process.cwd(), target),
});
const violations = result.messages.filter((message) => message.ruleId === "no-restricted-imports");

if (violations.length === 0) {
  console.error(`no zone violation reported for ${target}`);
  process.exit(1);
}

for (const violation of violations) {
  console.log(`${target}:${violation.line} ${violation.ruleId} ${violation.message}`);
}
