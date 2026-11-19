import { createApiClient } from "@erp/api-client";

import { clearToken, getToken } from "./storage";

export const CONTROLLER_API_URL =
  (import.meta.env.VITE_CONTROLLER_API_URL as string | undefined) || "http://localhost:8100";

export const SCHOOL_WEB_URL =
  (import.meta.env.VITE_SCHOOL_WEB_URL as string | undefined) || "http://localhost:5173";

export const API_PREFIX = "/controller/v1";

export const api = createApiClient({
  baseUrl: CONTROLLER_API_URL,
  getToken,
  onUnauthorized: clearToken,
  // Resolve `fetch` per request so tests can stub the global without re-creating
  // the client module.
  fetchImpl: (input, init) => fetch(input, init),
});

export function supportSessionUrl(token: string, reason: string): string {
  const params = new URLSearchParams({ token, reason });
  return `${SCHOOL_WEB_URL.replace(/\/$/, "")}/controller-login?${params.toString()}`;
}
