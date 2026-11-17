import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { VerifiedProfile } from "../directory/types";
import type { Locale } from "../i18n/ui-messages";
import {
  fetchMe,
  login as loginRequest,
  logoutSession,
  type SessionUser,
} from "../session/session";
import {
  forSchool,
  getActiveInstanceId,
  getVerifiedProfile,
  listProfiles,
  removeProfile,
  setActiveInstance,
} from "../storage/schoolStorage";
import type { ThemeMode } from "../theme/useSchoolTheme";

interface AppContextValue {
  ready: boolean;
  profile: VerifiedProfile | null;
  profiles: VerifiedProfile[];
  user: SessionUser | null;
  locale: Locale;
  mode: ThemeMode;
  refreshProfiles: () => Promise<void>;
  activateProfile: (instanceId: string) => Promise<VerifiedProfile>;
  removeSavedProfile: (instanceId: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<SessionUser>;
  signOut: () => Promise<void>;
  setLocale: (locale: Locale) => Promise<void>;
  setMode: (mode: ThemeMode) => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

function asLocale(value: string | null): Locale {
  return value === "am" ? "am" : "en";
}

function asMode(value: string | null): ThemeMode {
  return value === "dark" ? "dark" : "light";
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [profile, setProfile] = useState<VerifiedProfile | null>(null);
  const [profiles, setProfiles] = useState<VerifiedProfile[]>([]);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [locale, setLocaleState] = useState<Locale>("en");
  const [mode, setModeState] = useState<ThemeMode>("light");

  const loadPreferences = useCallback(async (nextProfile: VerifiedProfile) => {
    const store = forSchool(nextProfile.instanceId);
    setLocaleState(asLocale(await store.getPreference("locale")));
    setModeState(asMode(await store.getPreference("theme_mode")));
  }, []);

  const refreshProfiles = useCallback(async () => {
    setProfiles(await listProfiles());
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function boot(): Promise<void> {
      const saved = await listProfiles();
      if (!cancelled) setProfiles(saved);
      const activeId = await getActiveInstanceId();
      if (!activeId) {
        if (!cancelled) setReady(true);
        return;
      }
      const activeProfile = await getVerifiedProfile(activeId);
      if (!activeProfile) {
        if (!cancelled) setReady(true);
        return;
      }
      if (!cancelled) setProfile(activeProfile);
      await loadPreferences(activeProfile);
      const store = forSchool(activeId);
      const token = await store.getAccessToken();
      if (token) {
        try {
          const me = await fetchMe(activeId);
          if (!cancelled) setUser(me);
        } catch {
          await store.clearTokens();
        }
      }
      if (!cancelled) setReady(true);
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, [loadPreferences]);

  const activateProfile = useCallback(
    async (instanceId: string): Promise<VerifiedProfile> => {
      await setActiveInstance(instanceId);
      const nextProfile = await getVerifiedProfile(instanceId);
      if (!nextProfile) throw new Error("PROFILE_NOT_VERIFIED");
      setProfile(nextProfile);
      await loadPreferences(nextProfile);
      setUser(null);
      const store = forSchool(instanceId);
      if (await store.getAccessToken()) {
        try {
          setUser(await fetchMe(instanceId));
        } catch {
          await store.clearTokens();
        }
      }
      await refreshProfiles();
      return nextProfile;
    },
    [loadPreferences, refreshProfiles],
  );

  const removeSavedProfile = useCallback(
    async (instanceId: string) => {
      await removeProfile(instanceId);
      if (profile?.instanceId === instanceId) {
        setProfile(null);
        setUser(null);
      }
      await refreshProfiles();
    },
    [profile?.instanceId, refreshProfiles],
  );

  const signIn = useCallback(
    async (email: string, password: string): Promise<SessionUser> => {
      if (!profile) throw new Error("PROFILE_NOT_VERIFIED");
      const result = await loginRequest(profile.instanceId, email, password);
      setUser(result.user);
      return result.user;
    },
    [profile],
  );

  const signOut = useCallback(async () => {
    if (profile) {
      try {
        await logoutSession(profile.instanceId);
      } catch {
        // Signing out must always clear the local session.
      }
    }
    setUser(null);
  }, [profile]);

  const setLocale = useCallback(
    async (next: Locale) => {
      setLocaleState(next);
      if (profile) await forSchool(profile.instanceId).setPreference("locale", next);
    },
    [profile],
  );

  const setMode = useCallback(
    async (next: ThemeMode) => {
      setModeState(next);
      if (profile) await forSchool(profile.instanceId).setPreference("theme_mode", next);
    },
    [profile],
  );

  const value = useMemo<AppContextValue>(
    () => ({
      ready,
      profile,
      profiles,
      user,
      locale,
      mode,
      refreshProfiles,
      activateProfile,
      removeSavedProfile,
      signIn,
      signOut,
      setLocale,
      setMode,
    }),
    [
      ready,
      profile,
      profiles,
      user,
      locale,
      mode,
      refreshProfiles,
      activateProfile,
      removeSavedProfile,
      signIn,
      signOut,
      setLocale,
      setMode,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp must be used inside AppProvider");
  return context;
}
