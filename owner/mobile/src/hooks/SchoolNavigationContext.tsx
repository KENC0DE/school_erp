import { createContext, useContext, type ReactNode } from "react";

import type { VerifiedProfile } from "../directory/types";
import { useSchoolNavigation } from "./useSchoolNavigation";

type NavigationState = ReturnType<typeof useSchoolNavigation>;

const SchoolNavigationContext = createContext<NavigationState | null>(null);

export function SchoolNavigationProvider({
  profile,
  children,
}: {
  profile: VerifiedProfile;
  children: ReactNode;
}) {
  const navigation = useSchoolNavigation(profile);
  return (
    <SchoolNavigationContext.Provider value={navigation}>{children}</SchoolNavigationContext.Provider>
  );
}

export function useSchoolNavigationContext(): NavigationState {
  const context = useContext(SchoolNavigationContext);
  if (!context) throw new Error("useSchoolNavigationContext must be used inside its provider");
  return context;
}
