const ACCESS_KEY = "erp.access_token";
const REFRESH_KEY = "erp.refresh_token";
const LOCALE_KEY = "erp.locale";
const THEME_KEY = "erp.theme_mode";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function getStoredLocale(): string {
  return localStorage.getItem(LOCALE_KEY) ?? "en";
}

export function storeLocale(locale: string): void {
  localStorage.setItem(LOCALE_KEY, locale);
}

export function getStoredThemeMode(): "light" | "dark" {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function storeThemeMode(mode: "light" | "dark"): void {
  localStorage.setItem(THEME_KEY, mode);
}
