export type ThemeMode = "light" | "dark";

export interface TokenSet {
  background: string;
  foreground: string;
  card: string;
  "card-foreground": string;
  popover: string;
  "popover-foreground": string;
  primary: string;
  "primary-foreground": string;
  secondary: string;
  "secondary-foreground": string;
  muted: string;
  "muted-foreground": string;
  accent: string;
  "accent-foreground": string;
  destructive: string;
  "destructive-foreground": string;
  border: string;
  input: string;
  ring: string;
  "chart-1": string;
  "chart-2": string;
  "chart-3": string;
  "chart-4": string;
  "chart-5": string;
  sidebar: string;
  "sidebar-foreground": string;
  "sidebar-primary": string;
  "sidebar-primary-foreground": string;
  "sidebar-accent": string;
  "sidebar-accent-foreground": string;
  "sidebar-border": string;
  "sidebar-ring": string;
  radius: string;
  "font-sans": string;
  "font-ethiopic": string;
  [key: string]: string;
}

export interface ThemeDefinition {
  key: string;
  name: string;
  tokens: Record<ThemeMode, TokenSet>;
}

export const REQUIRED_TOKENS = [
  "background",
  "foreground",
  "card",
  "card-foreground",
  "popover",
  "popover-foreground",
  "primary",
  "primary-foreground",
  "secondary",
  "secondary-foreground",
  "muted",
  "muted-foreground",
  "accent",
  "accent-foreground",
  "destructive",
  "destructive-foreground",
  "border",
  "input",
  "ring",
  "chart-1",
  "chart-2",
  "chart-3",
  "chart-4",
  "chart-5",
  "sidebar",
  "sidebar-foreground",
  "sidebar-primary",
  "sidebar-primary-foreground",
  "sidebar-accent",
  "sidebar-accent-foreground",
  "sidebar-border",
  "sidebar-ring",
  "radius",
  "font-sans",
  "font-ethiopic",
] as const;

const light: TokenSet = {
  background: "oklch(1 0 0)",
  foreground: "oklch(0.145 0 0)",
  card: "oklch(1 0 0)",
  "card-foreground": "oklch(0.145 0 0)",
  popover: "oklch(1 0 0)",
  "popover-foreground": "oklch(0.145 0 0)",
  primary: "oklch(0.45 0.13 160)",
  "primary-foreground": "oklch(0.985 0 0)",
  secondary: "oklch(0.97 0 0)",
  "secondary-foreground": "oklch(0.205 0 0)",
  muted: "oklch(0.97 0 0)",
  "muted-foreground": "oklch(0.556 0 0)",
  accent: "oklch(0.95 0.04 85)",
  "accent-foreground": "oklch(0.205 0 0)",
  destructive: "oklch(0.577 0.245 27.325)",
  "destructive-foreground": "oklch(0.985 0 0)",
  border: "oklch(0.922 0 0)",
  input: "oklch(0.922 0 0)",
  ring: "oklch(0.45 0.13 160)",
  "chart-1": "oklch(0.646 0.222 41.116)",
  "chart-2": "oklch(0.6 0.118 184.704)",
  "chart-3": "oklch(0.398 0.07 227.392)",
  "chart-4": "oklch(0.828 0.189 84.429)",
  "chart-5": "oklch(0.769 0.188 70.08)",
  sidebar: "oklch(0.985 0 0)",
  "sidebar-foreground": "oklch(0.145 0 0)",
  "sidebar-primary": "oklch(0.45 0.13 160)",
  "sidebar-primary-foreground": "oklch(0.985 0 0)",
  "sidebar-accent": "oklch(0.97 0 0)",
  "sidebar-accent-foreground": "oklch(0.205 0 0)",
  "sidebar-border": "oklch(0.922 0 0)",
  "sidebar-ring": "oklch(0.708 0 0)",
  radius: "0.625rem",
  "font-sans": "Inter, 'Noto Sans Ethiopic', system-ui, sans-serif",
  "font-ethiopic": "'Noto Sans Ethiopic', sans-serif",
};

const dark: TokenSet = {
  background: "oklch(0.145 0 0)",
  foreground: "oklch(0.985 0 0)",
  card: "oklch(0.205 0 0)",
  "card-foreground": "oklch(0.985 0 0)",
  popover: "oklch(0.205 0 0)",
  "popover-foreground": "oklch(0.985 0 0)",
  primary: "oklch(0.62 0.13 160)",
  "primary-foreground": "oklch(0.145 0 0)",
  secondary: "oklch(0.269 0 0)",
  "secondary-foreground": "oklch(0.985 0 0)",
  muted: "oklch(0.269 0 0)",
  "muted-foreground": "oklch(0.708 0 0)",
  accent: "oklch(0.3 0.04 85)",
  "accent-foreground": "oklch(0.985 0 0)",
  destructive: "oklch(0.704 0.191 22.216)",
  "destructive-foreground": "oklch(0.985 0 0)",
  border: "oklch(1 0 0 / 12%)",
  input: "oklch(1 0 0 / 18%)",
  ring: "oklch(0.62 0.13 160)",
  "chart-1": "oklch(0.488 0.243 264.376)",
  "chart-2": "oklch(0.696 0.17 162.48)",
  "chart-3": "oklch(0.769 0.188 70.08)",
  "chart-4": "oklch(0.627 0.265 303.9)",
  "chart-5": "oklch(0.645 0.246 16.439)",
  sidebar: "oklch(0.205 0 0)",
  "sidebar-foreground": "oklch(0.985 0 0)",
  "sidebar-primary": "oklch(0.62 0.13 160)",
  "sidebar-primary-foreground": "oklch(0.145 0 0)",
  "sidebar-accent": "oklch(0.269 0 0)",
  "sidebar-accent-foreground": "oklch(0.985 0 0)",
  "sidebar-border": "oklch(1 0 0 / 12%)",
  "sidebar-ring": "oklch(0.556 0 0)",
  radius: "0.625rem",
  "font-sans": "Inter, 'Noto Sans Ethiopic', system-ui, sans-serif",
  "font-ethiopic": "'Noto Sans Ethiopic', sans-serif",
};

export const DEFAULT_THEME: ThemeDefinition = {
  key: "default",
  name: "Default",
  tokens: { light, dark },
};

export function validateTheme(theme: unknown): string[] {
  const problems: string[] = [];
  if (!theme || typeof theme !== "object") return ["Theme must be an object"];
  const candidate = theme as Partial<ThemeDefinition>;
  if (!candidate.tokens || typeof candidate.tokens !== "object") {
    return ["Theme must contain a tokens object"];
  }
  for (const mode of ["light", "dark"] as const) {
    const variant = candidate.tokens[mode];
    if (!variant || typeof variant !== "object") {
      problems.push(`Theme is missing the '${mode}' variant`);
      continue;
    }
    for (const token of REQUIRED_TOKENS) {
      const value = (variant as Record<string, unknown>)[token];
      if (typeof value !== "string" || value.trim() === "") {
        problems.push(`${mode} variant is missing token '${token}'`);
      }
    }
  }
  return problems;
}

export function toCssVariables(tokens: TokenSet): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const [key, value] of Object.entries(tokens)) {
    vars[key.startsWith("font-") || key === "radius" ? `--${key}` : `--${key}`] = value;
  }
  return vars;
}

export function cssVariableBlock(tokens: TokenSet): string {
  return Object.entries(toCssVariables(tokens))
    .map(([key, value]) => `  ${key}: ${value};`)
    .join("\n");
}

export function toReactNativeTheme(tokens: TokenSet) {
  return {
    colors: {
      background: tokens.background,
      foreground: tokens.foreground,
      card: tokens.card,
      cardForeground: tokens["card-foreground"],
      primary: tokens.primary,
      primaryForeground: tokens["primary-foreground"],
      secondary: tokens.secondary,
      muted: tokens.muted,
      mutedForeground: tokens["muted-foreground"],
      accent: tokens.accent,
      destructive: tokens.destructive,
      border: tokens.border,
      input: tokens.input,
      ring: tokens.ring,
      sidebar: tokens.sidebar,
      sidebarForeground: tokens["sidebar-foreground"],
      chart1: tokens["chart-1"],
      chart2: tokens["chart-2"],
      chart3: tokens["chart-3"],
      chart4: tokens["chart-4"],
      chart5: tokens["chart-5"],
    },
    radius: Number.parseFloat(tokens.radius) * 16,
    fonts: {
      sans: tokens["font-sans"],
      ethiopic: tokens["font-ethiopic"],
    },
  };
}

export type ReactNativeTheme = ReturnType<typeof toReactNativeTheme>;
