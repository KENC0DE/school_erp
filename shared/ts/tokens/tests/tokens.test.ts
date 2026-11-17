import { describe, expect, it } from "vitest";

import {
  DEFAULT_THEME,
  cssVariableBlock,
  toReactNativeTheme,
  validateTheme,
} from "../src";

describe("theme tokens", () => {
  it("accepts the shipped defaults", () => {
    expect(validateTheme(DEFAULT_THEME)).toEqual([]);
  });

  it("rejects a theme without a dark variant", () => {
    const broken = {
      key: "broken",
      name: "Broken",
      tokens: { light: DEFAULT_THEME.tokens.light },
    };
    expect(validateTheme(broken)).toContain("Theme is missing the 'dark' variant");
  });

  it("rejects a missing chart token", () => {
    const light = { ...DEFAULT_THEME.tokens.light } as Record<string, string>;
    delete light["chart-3"];
    const broken = { ...DEFAULT_THEME, tokens: { light, dark: DEFAULT_THEME.tokens.dark } };
    expect(validateTheme(broken).join(" ")).toContain("chart-3");
  });

  it("generates CSS variables and a React Native theme from one source", () => {
    const css = cssVariableBlock(DEFAULT_THEME.tokens.light);
    expect(css).toContain("--background: oklch(1 0 0);");
    expect(css).toContain("--sidebar-primary:");
    const native = toReactNativeTheme(DEFAULT_THEME.tokens.dark);
    expect(native.colors.background).toBe(DEFAULT_THEME.tokens.dark.background);
    expect(native.fonts.ethiopic).toContain("Noto Sans Ethiopic");
  });
});
