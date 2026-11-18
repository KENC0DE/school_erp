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

const noHardcodedStyle = {
  meta: {
    type: "problem",
    docs: {
      description: "Ban hard-coded colours, font sizes and spacing outside the design tokens.",
    },
    schema: [],
    messages: {
      colour: "Hard-coded colour \"{{value}}\" is not allowed. Use a theme token or a kit class.",
      arbitrary:
        "Arbitrary Tailwind value \"{{value}}\" is not allowed. Use a design token or a shared kit class.",
      palette:
        "Tailwind palette colour \"{{value}}\" is not allowed. Use a semantic token (primary, muted, destructive, …).",
    },
  },
  create(context) {
    const patterns = [
      { id: "colour", re: /#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|oklch|oklab|lab|lch)\(/g },
      {
        id: "arbitrary",
        re: /\b(?:bg|text|border|ring|fill|stroke|shadow|p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap|space-[xy]|w|h|min-w|min-h|max-w|max-h|size|rounded|leading|tracking)-\[[^\]]+\]/g,
      },
      {
        id: "palette",
        re: /\b(?:bg|text|border|ring|fill|stroke)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/g,
      },
    ];
    const check = (node, value) => {
      for (const pattern of patterns) {
        pattern.re.lastIndex = 0;
        const match = pattern.re.exec(value);
        if (match) {
          context.report({ node, messageId: pattern.id, data: { value: match[0] } });
          return;
        }
      }
    };
    return {
      JSXAttribute(node) {
        if (node.name?.name !== "className" && node.name?.name !== "style") return;
        if (node.value?.type === "Literal" && typeof node.value.value === "string") {
          check(node.value, node.value.value);
          return;
        }
        if (node.value?.type === "JSXExpressionContainer") {
          const seen = new Set();
          const visit = (child) => {
            if (!child || typeof child !== "object" || seen.has(child)) return;
            seen.add(child);
            if (child.type === "Literal" && typeof child.value === "string") check(child, child.value);
            if (child.type === "TemplateElement") check(child, child.value.raw);
            for (const [key, value] of Object.entries(child)) {
              if (key === "parent") continue;
              if (Array.isArray(value)) value.forEach(visit);
              else if (value && typeof value === "object" && typeof value.type === "string") visit(value);
            }
          };
          visit(node.value.expression);
        }
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
    files: [
      "school-erp/web/src/**/*.{ts,tsx}",
      "owner/controller-web/src/**/*.{ts,tsx}",
      "shared/ts/ui-web/src/**/*.{ts,tsx}",
    ],
    ignores: ["**/*.test.{ts,tsx}", "**/*.spec.{ts,tsx}"],
    plugins: { design: { rules: { "no-hardcoded-style": noHardcodedStyle } } },
    rules: { "design/no-hardcoded-style": "error" },
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
