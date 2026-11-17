import { DEFAULT_THEME, validateTheme, type ThemeDefinition } from "@erp/tokens";
import { useEffect, useMemo, useState } from "react";

import type { VerifiedProfile } from "../directory/types";
import { forSchool, getVerifiedBaseUrl } from "../storage/schoolStorage";
import { nativeThemeFrom } from "./nativeTheme";

export type ThemeMode = "light" | "dark";

export interface SchoolTheme {
  theme: ThemeDefinition;
  rn: ReturnType<typeof nativeThemeFrom>;
  source: "default" | "school" | "user";
}

const SHIPPED: ThemeDefinition = DEFAULT_THEME;

/**
 * Loads the active theme for this device.
 *
 * The school default is public so the login screen can be branded before a
 * session exists. Once signed in the access token is sent too, which makes the
 * backend resolve the user's own theme choice (P1-21). A failure at any point
 * keeps the cached or shipped default so the app never renders unstyled.
 */
export function useSchoolTheme(profile: VerifiedProfile | null, mode: ThemeMode): SchoolTheme {
  const [theme, setTheme] = useState<ThemeDefinition>(SHIPPED);
  const [source, setSource] = useState<SchoolTheme["source"]>("default");

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
        const token = await store.getAccessToken();
        const headers: Record<string, string> = { Accept: "application/json" };
        if (token) headers.Authorization = `Bearer ${token}`;
        const response = await fetch(`${baseUrl}/api/v1/themes/active`, { headers });
        if (!response.ok) return;
        const data = (await response.json()) as Partial<ThemeDefinition> & { source?: string };
        const candidate: ThemeDefinition = {
          key: typeof data.key === "string" ? data.key : "school",
          name: typeof data.name === "string" ? data.name : "School",
          tokens: data.tokens as ThemeDefinition["tokens"],
        };
        if (validateTheme(candidate).length > 0) {
          if (!cancelled) {
            setTheme(SHIPPED);
            setSource("default");
          }
          return;
        }
        if (!cancelled) {
          setTheme(candidate);
          setSource(data.source === "user" ? "user" : "school");
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
