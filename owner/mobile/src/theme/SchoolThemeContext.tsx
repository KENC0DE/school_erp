import { createContext, useContext, type ReactNode } from "react";

import type { VerifiedProfile } from "../directory/types";
import { useSchoolTheme, type SchoolTheme, type ThemeMode } from "./useSchoolTheme";

const SchoolThemeContext = createContext<SchoolTheme | null>(null);

export function SchoolThemeProvider({
  profile,
  mode,
  children,
}: {
  profile: VerifiedProfile | null;
  mode: ThemeMode;
  children: ReactNode;
}) {
  const theme = useSchoolTheme(profile, mode);
  return <SchoolThemeContext.Provider value={theme}>{children}</SchoolThemeContext.Provider>;
}

export function useSchoolThemeContext(): SchoolTheme {
  const context = useContext(SchoolThemeContext);
  if (!context) throw new Error("useSchoolThemeContext must be used inside SchoolThemeProvider");
  return context;
}
