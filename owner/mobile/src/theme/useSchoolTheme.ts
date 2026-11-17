import { DEFAULT_THEME, validateTheme, type ThemeDefinition } from "@erp/tokens";
import { useEffect, useMemo, useState } from "react";

import type { VerifiedProfile } from "../directory/types";
import { forSchool, getVerifiedBaseUrl } from "../storage/schoolStorage";
import { nativeThemeFrom } from "./nativeTheme";

export type ThemeMode = "light" | "dark";

export interface SchoolTheme {
  theme: ThemeDefinition;
  rn: ReturnType<typeof nativeThemeFrom>;
  source: "default" | "school";
}

/**
 * Loads the school's active theme, validates both variants and always exposes a
 * React Native theme object. Any failure falls back to DEFAULT_THEME.
 */
export function useSchoolTheme(profile: VerifiedProfile | null, mode: ThemeMode): SchoolTheme {
  const [theme, setTheme] = useState<ThemeDefinition>(DEFAULT_THEME);
  const [source, setSource] = useState<"default" | "school">("default");

  useEffect(() => {
    if (!profile) return;
    let cancelled = false;
    const store = forSchool(profile.instanceId);

    async function run(): Promise<void> {
      const cached = await store.getCache<ThemeDefinition>("theme");
      if (!cancelled && cached && validateTheme(cached).length === 0) {
        setTheme(cached);
        setSource("school");
      }
      try {
        const baseUrl = await getVerifiedBaseUrl(profile!.instanceId);
        const response = await fetch(`${baseUrl}/api/v1/themes/active`, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) return;
        const data = (await response.json()) as Partial<ThemeDefinition>;
        const candidate: ThemeDefinition = {
          key: typeof data.key === "string" ? data.key : "school",
          name: typeof data.name === "string" ? data.name : "School",
          tokens: data.tokens as ThemeDefinition["tokens"],
        };
        if (validateTheme(candidate).length > 0) {
          if (!cancelled) {
            setTheme(DEFAULT_THEME);
            setSource("default");
          }
          return;
        }
        if (!cancelled) {
          setTheme(candidate);
          setSource("school");
        }
        await store.setCache("theme", candidate);
      } catch {
        // Keep the cached or shipped default theme.
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [profile?.instanceId]);

  const rn = useMemo(() => nativeThemeFrom(theme, mode), [theme, mode]);

  return { theme, rn, source };
}
