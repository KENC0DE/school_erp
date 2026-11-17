import { createContext, useContext, type ReactNode } from "react";

import type { VerifiedProfile } from "../directory/types";
import { useSchoolTranslations, type SchoolTranslations } from "./useSchoolTranslations";
import type { Locale } from "./ui-messages";

const SchoolI18nContext = createContext<SchoolTranslations | null>(null);

export function SchoolI18nProvider({
  profile,
  locale,
  children,
}: {
  profile: VerifiedProfile | null;
  locale: Locale;
  children: ReactNode;
}) {
  const translations = useSchoolTranslations(profile, locale);
  return <SchoolI18nContext.Provider value={translations}>{children}</SchoolI18nContext.Provider>;
}

export function useSchoolI18n(): SchoolTranslations {
  const context = useContext(SchoolI18nContext);
  if (!context) throw new Error("useSchoolI18n must be used inside SchoolI18nProvider");
  return context;
}
