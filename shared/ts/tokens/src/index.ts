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
  "muted-foreground": "oklch(0.53 0 0)",
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
  destructive: "oklch(0.577 0.245 27.325)",
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

/**
 * Design foundation scales (ARCH §11.5). Colour, radius and fonts live in the
 * theme tokens so a school can change them; spacing, type sizes, shadows and
 * layout are fixed across themes so a theme can never break a layout.
 */
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 24,
  xl: 32,
  "2xl": 48,
  "3xl": 64,
} as const;

export const SPACING_SCALE = [4, 8, 12, 16, 24, 32, 48, 64] as const;

export const fontSize = {
  xs: 12,
  sm: 14,
  base: 16,
  md: 18,
  lg: 20,
  xl: 24,
  "2xl": 30,
} as const;

export const fontWeight = {
  regular: 400,
  medium: 500,
  semibold: 600,
} as const;

export const lineHeight = {
  tight: 1.4,
  normal: 1.5,
  relaxed: 1.6,
} as const;

export const shadows = {
  none: "none",
  sm: "0 1px 2px 0 oklch(0 0 0 / 6%)",
  md: "0 4px 12px -2px oklch(0 0 0 / 10%)",
  lg: "0 12px 32px -8px oklch(0 0 0 / 18%)",
} as const;

export const breakpoints = {
  phoneMax: 639,
  tabletMin: 640,
  desktopMin: 1025,
} as const;

export const layout = {
  pagePaddingMobile: 16,
  pagePaddingDesktop: 24,
  cardPaddingMin: 16,
  cardPaddingMax: 24,
  sidebarWidth: 264,
  sidebarRailWidth: 72,
  topBarHeight: 64,
  contentMaxWidth: 1280,
  formMaxWidth: 720,
  radius: 8,
} as const;

export const touchTarget = {
  ios: 44,
  android: 48,
} as const;

export const motion = {
  fast: 150,
  normal: 200,
} as const;

export const designTokens = {
  spacing,
  fontSize,
  fontWeight,
  lineHeight,
  shadows,
  breakpoints,
  layout,
  touchTarget,
  motion,
} as const;

export function px(value: number): string {
  return `${value}px`;
}

export function spacingVar(key: keyof typeof spacing): string {
  return `var(--space-${key})`;
}

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
