import { forSchool, getVerifiedBaseUrl } from "../storage/schoolStorage";

export interface SessionUser {
  id: string;
  email: string | null;
  display_name: string;
  locale: string;
  roles: string[];
  permissions: string[];
  actor_type?: string;
  is_controller?: boolean;
  read_only?: boolean;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in: number;
}

export interface LoginResult {
  tokens: TokenPair;
  user: SessionUser;
}

export interface NavItem {
  key: string;
  label_key: string;
  path: string;
  icon?: string;
  module: string;
}

export interface Navigation {
  items: NavItem[];
  modules: string[];
  locale: string;
  languages: string[];
}

export type SessionErrorCode =
  | "PROFILE_NOT_VERIFIED"
  | "INVALID_CREDENTIALS"
  | "NO_REFRESH_TOKEN"
  | "UNAUTHORIZED"
  | "NETWORK_ERROR"
  | "INVALID_RESPONSE"
  | "HTTP_ERROR";

export class SessionError extends Error {
  constructor(
    public readonly code: SessionErrorCode | string,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "SessionError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  authenticated?: boolean;
  retryOnUnauthorized?: boolean;
}

export interface SessionDeps {
  fetcher?: typeof fetch;
}

function jsonHeaders(authenticated: boolean, token: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    "X-Client-Via": "mobile",
  };
  if (authenticated && token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function readError(response: Response): Promise<SessionError> {
  let code = "HTTP_ERROR";
  try {
    const payload = (await response.json()) as { error?: { code?: string } };
    if (payload.error?.code) code = payload.error.code;
  } catch {
    // Non-JSON errors keep the generic code.
  }
  if (response.status === 401 || response.status === 403) {
    if (code === "HTTP_ERROR") code = response.status === 401 ? "UNAUTHORIZED" : "PERMISSION_DENIED";
  }
  return new SessionError(code, `Request failed with ${response.status}`, response.status);
}

async function perform(
  instanceId: string,
  path: string,
  options: RequestOptions & SessionDeps,
): Promise<Response> {
  let baseUrl: string;
  try {
    baseUrl = await getVerifiedBaseUrl(instanceId);
  } catch {
    throw new SessionError("PROFILE_NOT_VERIFIED", "School is not a verified profile");
  }
  const store = forSchool(instanceId);
  const authenticated = options.authenticated !== false;
  const token = authenticated ? await store.getAccessToken() : null;
  const fetcher = options.fetcher ?? fetch;
  let response: Response;
  try {
    response = await fetcher(`${baseUrl}${path}`, {
      method: options.method ?? "GET",
      headers: { ...jsonHeaders(authenticated, token), ...options.headers },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new SessionError("NETWORK_ERROR", "Cannot reach the school server");
  }
  if (response.status === 401 && authenticated && options.retryOnUnauthorized !== false) {
    try {
      await refreshSession(instanceId, { fetcher });
    } catch {
      await store.clearTokens();
      throw new SessionError("UNAUTHORIZED", "Session expired", 401);
    }
    return perform(instanceId, path, {
      ...options,
      retryOnUnauthorized: false,
    });
  }
  return response;
}

function assertTokenPair(value: unknown): TokenPair {
  const pair = value as Partial<TokenPair> | null;
  if (
    !pair ||
    typeof pair.access_token !== "string" ||
    typeof pair.refresh_token !== "string" ||
    typeof pair.expires_in !== "number"
  ) {
    throw new SessionError("INVALID_RESPONSE", "Server returned an invalid token pair");
  }
  return pair as TokenPair;
}

/** Logs in against the school's verified api_base_url. No URL parameter exists by design. */
export async function login(
  instanceId: string,
  email: string,
  password: string,
  deps: SessionDeps = {},
): Promise<LoginResult> {
  const response = await perform(instanceId, "/api/v1/auth/login", {
    method: "POST",
    body: { email: email.trim().toLowerCase(), password },
    authenticated: false,
    fetcher: deps.fetcher,
  });
  if (response.status === 401 || response.status === 403) {
    throw new SessionError("INVALID_CREDENTIALS", "Email or password is incorrect", response.status);
  }
  if (!response.ok) throw await readError(response);
  let data: LoginResult;
  try {
    data = (await response.json()) as LoginResult;
  } catch {
    throw new SessionError("INVALID_RESPONSE", "Server returned invalid JSON");
  }
  const tokens = assertTokenPair(data.tokens);
  if (!data.user || typeof data.user.id !== "string") {
    throw new SessionError("INVALID_RESPONSE", "Server returned no user");
  }
  await forSchool(instanceId).setTokens({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  });
  return { tokens, user: data.user };
}

export async function refreshSession(
  instanceId: string,
  deps: SessionDeps = {},
): Promise<TokenPair> {
  const store = forSchool(instanceId);
  const refreshToken = await store.getRefreshToken();
  if (!refreshToken) throw new SessionError("NO_REFRESH_TOKEN", "No refresh token is stored");
  let baseUrl: string;
  try {
    baseUrl = await getVerifiedBaseUrl(instanceId);
  } catch {
    throw new SessionError("PROFILE_NOT_VERIFIED", "School is not a verified profile");
  }
  const fetcher = deps.fetcher ?? fetch;
  let response: Response;
  try {
    response = await fetcher(`${baseUrl}/api/v1/auth/refresh`, {
      method: "POST",
      headers: jsonHeaders(false, null),
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    throw new SessionError("NETWORK_ERROR", "Cannot reach the school server");
  }
  if (!response.ok) {
    if (response.status === 401) await store.clearTokens();
    throw await readError(response);
  }
  const tokens = assertTokenPair(await response.json());
  await store.setTokens({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  });
  return tokens;
}

export async function logoutSession(instanceId: string, deps: SessionDeps = {}): Promise<void> {
  const store = forSchool(instanceId);
  const token = await store.getAccessToken();
  if (token) {
    try {
      await perform(instanceId, "/api/v1/auth/logout", {
        method: "POST",
        fetcher: deps.fetcher,
        retryOnUnauthorized: false,
      });
    } catch {
      // Local sign-out must always succeed.
    }
  }
  await store.clearTokens();
}

export async function authorizedJson<T>(
  instanceId: string,
  path: string,
  init: RequestOptions & SessionDeps = {},
): Promise<T> {
  const response = await perform(instanceId, path, init);
  if (!response.ok) throw await readError(response);
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new SessionError("INVALID_RESPONSE", "Server returned invalid JSON");
  }
}

export async function fetchMe(instanceId: string, deps: SessionDeps = {}): Promise<SessionUser> {
  return authorizedJson<SessionUser>(instanceId, "/api/v1/auth/me", deps);
}

export async function fetchNavigation(
  instanceId: string,
  deps: SessionDeps = {},
): Promise<Navigation> {
  return authorizedJson<Navigation>(instanceId, "/api/v1/auth/me/navigation", deps);
}
