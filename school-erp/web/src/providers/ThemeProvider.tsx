import { DEFAULT_THEME, type ThemeDefinition } from "@erp/tokens";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "../lib/api";
import { getAccessToken, getStoredThemeMode, storeThemeMode } from "../lib/storage";
import { useAuth } from "./AuthProvider";

type Mode = "light" | "dark";

export interface ThemeSummary {
  key: string;
  name: string;
  description: string | null;
  is_default: boolean;
  is_active: boolean;
  is_builtin: boolean;
  valid: boolean;
}

interface ActiveTheme extends ThemeDefinition {
  source: string;
  mode: Mode | null;
  user_theme_key: string | null;
  fallback: boolean;
}

interface ThemeState {
  mode: Mode;
  setMode: (mode: Mode) => void;
  toggle: () => void;
  theme: ThemeDefinition;
  themeKey: string | null;
  available: ThemeSummary[];
  setThemeKey: (key: string | null) => Promise<void>;
  reload: () => Promise<void>;
}

const ThemeContext = createContext<ThemeState | null>(null);

function applyTokens(theme: ThemeDefinition, mode: Mode): void {
  const root = document.documentElement;
  // Start from the shipped tokens so a theme that omits an optional property
  // cannot leave a stale value from the previous theme behind.
  for (const [key, value] of Object.entries(DEFAULT_THEME.tokens[mode])) {
    root.style.setProperty(`--${key}`, value);
  }
  const tokens = theme.tokens[mode] ?? DEFAULT_THEME.tokens[mode];
  for (const [key, value] of Object.entries(tokens)) {
    root.style.setProperty(`--${key}`, value);
  }
  root.classList.toggle("dark", mode === "dark");
  root.dataset.theme = theme.key;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [mode, setModeState] = useState<Mode>(getStoredThemeMode());
  const [theme, setTheme] = useState<ThemeDefinition>(DEFAULT_THEME);
  const [themeKey, setThemeKeyState] = useState<string | null>(null);
  const [available, setAvailable] = useState<ThemeSummary[]>([]);

  const reload = useCallback(async () => {
    const token = getAccessToken();
    try {
      const active = await api.get<ActiveTheme>("/api/v1/themes/active");
      if (active?.tokens?.light && active?.tokens?.dark) {
        setTheme({ key: active.key, name: active.name, tokens: active.tokens });
        setThemeKeyState(active.user_theme_key ?? null);
        if (token && (active.mode === "light" || active.mode === "dark")) {
          setModeState(active.mode);
        }
      }
    } catch {
      // A broken or unreachable theme always falls back to the shipped default.
    }
    if (!token) {
      setAvailable([]);
      return;
    }
    try {
      const list = await api.get<{ items: ThemeSummary[] }>("/api/v1/themes/available");
      setAvailable(list.items);
    } catch {
      setAvailable([]);
    }
  }, []);

  // Re-resolve after sign-in and sign-out so the user's own theme (or the
  // school default for anonymous visitors) is applied without a page reload.
  useEffect(() => {
    void reload();
  }, [reload, token]);

  useEffect(() => {
    applyTokens(theme, mode);
    storeThemeMode(mode);
  }, [theme, mode]);

  const persist = useCallback(
    (nextMode: Mode, nextKey: string | null) => {
      if (!getAccessToken()) return;
      void api
        .put("/api/v1/themes/preference", { theme_key: nextKey, mode: nextMode })
        .catch(() => undefined);
    },
    [],
  );

  const setMode = useCallback(
    (next: Mode) => {
      setModeState(next);
      persist(next, themeKey);
    },
    [persist, themeKey],
  );
  const toggle = useCallback(() => {
    setModeState((current) => {
      const next = current === "light" ? "dark" : "light";
      persist(next, themeKey);
      return next;
    });
  }, [persist, themeKey]);

  const setThemeKey = useCallback(
    async (key: string | null) => {
      const result = await api.put<{ theme_key: string | null }>("/api/v1/themes/preference", {
        theme_key: key,
        mode,
      });
      setThemeKeyState(result.theme_key);
      await reload();
    },
    [mode, reload],
  );

  const value = useMemo(
    () => ({ mode, setMode, toggle, theme, themeKey, available, setThemeKey, reload }),
    [mode, setMode, toggle, theme, themeKey, available, setThemeKey, reload],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
