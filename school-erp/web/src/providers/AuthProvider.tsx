import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, type LoginResult, type SessionUser } from "../lib/api";
import { clearTokens, getAccessToken, setTokens } from "../lib/storage";

interface AuthState {
  user: SessionUser | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  adoptSession: (result: LoginResult) => void;
  controllerLogin: (supportToken: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [token, setToken] = useState<string | null>(getAccessToken());
  const [loading, setLoading] = useState(Boolean(getAccessToken()));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const existing = getAccessToken();
    if (!existing) return;
    let cancelled = false;
    api
      .get<SessionUser>("/api/v1/auth/me")
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (!cancelled) {
          clearTokens();
          setToken(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const result = await api.post<LoginResult>("/api/v1/auth/login", { email, password });
    setTokens(result.tokens.access_token, result.tokens.refresh_token);
    setToken(result.tokens.access_token);
    setUser(result.user);
  }, []);

  // The setup wizard returns a full session so the first Super Admin lands on
  // the dashboard without a second sign-in round trip.
  const adoptSession = useCallback((result: LoginResult) => {
    setTokens(result.tokens.access_token, result.tokens.refresh_token);
    setToken(result.tokens.access_token);
    setUser(result.user);
  }, []);

  const controllerLogin = useCallback(async (supportToken: string) => {
    setError(null);
    const result = await api.post<{ access_token: string; token_type: string; expires_in: number }>(
      "/api/v1/auth/controller-session",
      { token: supportToken },
    );
    // Support sessions are short-lived and cannot be refreshed; only the
    // access token is stored so a stale refresh token can never be replayed.
    setTokens(result.access_token, "");
    setToken(result.access_token);
    const me = await api.get<SessionUser>("/api/v1/auth/me");
    setUser(me);
  }, []);

  const refresh = useCallback(async () => {
    const me = await api.get<SessionUser>("/api/v1/auth/me");
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/v1/auth/logout");
    } catch {
      // Local sign-out must work even when the server is unreachable.
    }
    clearTokens();
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, loading, error, login, adoptSession, controllerLogin, logout, refresh }),
    [user, token, loading, error, login, adoptSession, controllerLogin, logout, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function setAuthError(message: string | null): void {
  // Reserved for form-level mapping once the login form is extracted.
  void message;
}
