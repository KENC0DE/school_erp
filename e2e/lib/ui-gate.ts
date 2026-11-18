import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * Every screen whose main content comes from the API must show a loading
 * skeleton, an empty state and an error state with a retry action (UI
 * checklist §3). The check is static on purpose: it catches a screen that
 * forgot a state even when the happy path is what the e2e run exercises.
 */
export const DATA_SCREENS = [
  "school-erp/web/src/pages/Dashboard.tsx",
  "school-erp/web/src/pages/ActivityPage.tsx",
  "school-erp/web/src/pages/UsersPage.tsx",
  "school-erp/web/src/pages/RolesPage.tsx",
  "school-erp/web/src/pages/ModulesPage.tsx",
  "school-erp/web/src/pages/NotificationsPage.tsx",
  "school-erp/web/src/pages/JobsPage.tsx",
  "school-erp/web/src/pages/SamplePage.tsx",
  "school-erp/web/src/pages/TranslationsPage.tsx",
  "school-erp/web/src/pages/ThemeManagerPage.tsx",
  "school-erp/web/src/pages/academics/YearsPanel.tsx",
  "school-erp/web/src/pages/academics/SubjectsPanel.tsx",
  "school-erp/web/src/pages/academics/SectionsPanel.tsx",
  "school-erp/web/src/pages/academics/CurriculumPanel.tsx",
  "school-erp/web/src/pages/academics/ScopePanel.tsx",
  "school-erp/web/src/pages/students/StudentsPage.tsx",
  "school-erp/web/src/pages/students/StudentProfilePage.tsx",
  "school-erp/web/src/pages/students/PromotionPage.tsx",
  "school-erp/web/src/pages/admissions/AdmissionsPage.tsx",
  "school-erp/web/src/pages/admissions/ApplicationProfilePage.tsx",
  "school-erp/web/src/pages/admissions/PublicApplicationPage.tsx",
] as const;

const REQUIRED_STATES = ["LoadingState", "EmptyState", "ErrorState"] as const;

export interface ScreenStateGap {
  file: string;
  missing: string[];
}

export function screenStateGaps(
  repoRoot: string,
  files: readonly string[] = DATA_SCREENS,
): ScreenStateGap[] {
  const gaps: ScreenStateGap[] = [];
  for (const file of files) {
    const source = readFileSync(path.join(repoRoot, file), "utf8");
    const missing = REQUIRED_STATES.filter((state) => !source.includes(state));
    if (missing.length > 0) gaps.push({ file, missing });
  }
  return gaps;
}

export function checkScreenStates(
  repoRoot: string,
  files: readonly string[] = DATA_SCREENS,
): ScreenStateGap[] {
  const gaps = screenStateGaps(repoRoot, files);
  if (gaps.length > 0) {
    const detail = gaps
      .map((gap) => `  ${gap.file}: missing ${gap.missing.join(", ")}`)
      .join("\n");
    throw new Error(`Data screens without all UI states:\n${detail}`);
  }
  return gaps;
}

/** A deliberately low-contrast theme: text and background are the same. */
export function lowContrastCss(
  tokens: Record<string, Record<string, string>>,
): string {
  const light = { ...tokens.light, foreground: tokens.light?.background ?? "" };
  const dark = { ...tokens.dark, foreground: tokens.dark?.background ?? "" };
  return cssFrom(light ?? {}, dark ?? {});
}

/** A valid community theme: same layout, different brand colour. */
export function recolouredCss(
  tokens: Record<string, Record<string, string>>,
): string {
  const light = { ...tokens.light, primary: "oklch(0.52 0.16 30)" };
  const dark = { ...tokens.dark, primary: "oklch(0.7 0.14 30)" };
  return cssFrom(light ?? {}, dark ?? {});
}

function cssFrom(
  light: Record<string, string>,
  dark: Record<string, string>,
): string {
  const block = (variant: Record<string, string>) =>
    Object.entries(variant)
      .map(([key, value]) => `  --${key}: ${value};`)
      .join("\n");
  return `:root {\n${block(light)}\n}\n.dark {\n${block(dark)}\n}\n`;
}
