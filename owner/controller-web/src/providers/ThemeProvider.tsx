import { DEFAULT_THEME } from "@erp/tokens";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getStoredThemeMode, storeThemeMode } from "../lib/storage";

type Mode = "light" | "dark";

interface ThemeState {
  mode: Mode;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

function applyTokens(mode: Mode): void {
  const tokens = DEFAULT_THEME.tokens[mode];
  const root = document.documentElement;
  for (const [key, value] of Object.entries(tokens)) {
    root.style.setProperty(`--${key}`, value);
  }
  root.classList.toggle("dark", mode === "dark");
  root.dataset.theme = DEFAULT_THEME.key;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(getStoredThemeMode);

  useEffect(() => {
    applyTokens(mode);
    storeThemeMode(mode);
  }, [mode]);

  const toggle = useCallback(
    () => setMode((current) => (current === "light" ? "dark" : "light")),
    [],
  );

  const value = useMemo(() => ({ mode, toggle }), [mode, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
