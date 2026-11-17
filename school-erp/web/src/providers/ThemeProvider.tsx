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
import { getStoredThemeMode, storeThemeMode } from "../lib/storage";

type Mode = "light" | "dark";

interface ThemeState {
  mode: Mode;
  setMode: (mode: Mode) => void;
  toggle: () => void;
  theme: ThemeDefinition;
}

const ThemeContext = createContext<ThemeState | null>(null);

function applyTokens(theme: ThemeDefinition, mode: Mode): void {
  const tokens = theme.tokens[mode] ?? DEFAULT_THEME.tokens[mode];
  const root = document.documentElement;
  for (const [key, value] of Object.entries(tokens)) {
    root.style.setProperty(`--${key}`, value);
  }
  root.classList.toggle("dark", mode === "dark");
  root.dataset.theme = theme.key;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>(getStoredThemeMode());
  const [theme, setTheme] = useState<ThemeDefinition>(DEFAULT_THEME);

  useEffect(() => {
    let cancelled = false;
    api
      .get<ThemeDefinition & { source: string }>("/api/v1/themes/active")
      .then((active) => {
        if (!cancelled && active?.tokens?.light && active?.tokens?.dark) {
          setTheme({ key: active.key, name: active.name, tokens: active.tokens });
        }
      })
      .catch(() => {
        // A broken or unreachable theme always falls back to the shipped default.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    applyTokens(theme, mode);
    storeThemeMode(mode);
  }, [theme, mode]);

  const setMode = useCallback((next: Mode) => setModeState(next), []);
  const toggle = useCallback(() => setModeState((current) => (current === "light" ? "dark" : "light")), []);

  const value = useMemo(() => ({ mode, setMode, toggle, theme }), [mode, setMode, toggle, theme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
