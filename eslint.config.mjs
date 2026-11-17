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

const noLiteralUiText = {
  meta: {
    type: "problem",
    docs: {
      description: "Ban hard-coded user-facing text in JSX; use t('key') instead.",
    },
    schema: [],
    messages: {
      literal:
        "Hard-coded UI text \"{{text}}\" is not allowed. Move it to an i18n bundle and use t().",
    },
  },
  create(context) {
    const namedAttributes = new Set(["title", "placeholder", "aria-label", "alt", "label"]);
    const decorative = (node) => {
      const attributes = node.parent?.attributes ?? [];
      return attributes.some(
        (attribute) =>
          attribute.type === "JSXAttribute" &&
          attribute.name?.name === "aria-hidden" &&
          attribute.value?.value === "true",
      );
    };
    const report = (node, value) => {
      const text = value.trim();
      if (!text || !/\p{L}/u.test(text)) return;
      if (decorative(node)) return;
      context.report({ node, messageId: "literal", data: { text } });
    };
    return {
      JSXText(node) {
        report(node, node.value);
      },
      JSXAttribute(node) {
        if (!namedAttributes.has(node.name?.name)) return;
        if (node.value?.type !== "Literal" || typeof node.value.value !== "string") return;
        report(node.value, node.value.value);
      },
    };
  },
};

export default [
  { ignores: ["**/dist/**", "**/node_modules/**", "**/.expo/**", "**/coverage/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: { "@typescript-eslint/no-explicit-any": "off" },
  },
  {
    files: [
      "school-erp/web/src/**/*.{ts,tsx}",
      "owner/controller-web/src/**/*.{ts,tsx}",
      "owner/mobile/app/**/*.{ts,tsx}",
      "owner/mobile/src/**/*.{ts,tsx}",
    ],
    ignores: ["**/*.test.{ts,tsx}", "**/*.spec.{ts,tsx}"],
    plugins: { i18n: { rules: { "no-literal-ui-text": noLiteralUiText } } },
    rules: { "i18n/no-literal-ui-text": "error" },
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
