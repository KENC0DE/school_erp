const TOKEN_KEY = "erp.controller.access_token";
const THEME_KEY = "erp.controller.theme_mode";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function getStoredThemeMode(): "light" | "dark" {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function storeThemeMode(mode: "light" | "dark"): void {
  localStorage.setItem(THEME_KEY, mode);
}
