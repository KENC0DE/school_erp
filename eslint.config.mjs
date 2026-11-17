// Zone boundaries for the TypeScript half of the repo (ARCH §4.4).
// CI and pre-commit run this at the workspace root.
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

const ban = (zones) => ({
  "no-restricted-imports": [
    "error",
    {
      patterns: zones.map((z) => ({
        group: z.group,
        message: `Zone boundary violation: ${z.message}`,
      })),
    },
  ],
});

export default [
  { ignores: ["**/dist/**", "**/node_modules/**", "**/.expo/**", "**/coverage/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: { "@typescript-eslint/no-explicit-any": "off" },
  },
  {
    files: ["school-erp/web/**/*.{ts,tsx}"],
    rules: ban([{ group: ["**/owner/**", "@erp/mobile*", "@erp/controller-*"], message: "school-erp must not import owner/" }]),
  },
  {
    files: ["owner/controller-web/**/*.{ts,tsx}", "owner/mobile/**/*.{ts,tsx}"],
    rules: ban([{ group: ["**/school-erp/**"], message: "owner may only use shared/ and HTTP APIs" }]),
  },
  {
    files: ["shared/ts/**/*.{ts,tsx}"],
    rules: ban([
      { group: ["**/school-erp/**", "**/owner/**"], message: "shared must not import another zone" },
    ]),
  },
];
