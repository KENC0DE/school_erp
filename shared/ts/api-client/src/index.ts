import type { paths } from "./schema";

export type { paths };

/** The standard error envelope every API returns (ARCH §5.1). */
export interface ApiError {
  error: {
    code: string;
    message_key?: string;
    message: string;
    details?: unknown;
    request_id?: string;
  };
}

export interface ApiClientOptions {
  baseUrl: string;
  getToken?: () => string | null | undefined;
  fetchImpl?: typeof fetch;
  onUnauthorized?: () => void;
  /** Optional caller hint used for audit (`via`). Omit to let the server decide. */
  clientVia?: string;
}

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export function createApiClient(options: ApiClientOptions) {
  // Resolve fetch at call time so tests can stub the global after importing
  // this module, and so environments that patch fetch keep working.
  const doFetch = (...args: Parameters<typeof fetch>) =>
    (options.fetchImpl ?? globalThis.fetch)(...args);
  const baseUrl = options.baseUrl.replace(/\/$/, "");

  async function request<T>(
    method: string,
    path: string,
    body?: unknown,
    extraHeaders?: Record<string, string>,
    formBody = false,
  ): Promise<T> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...extraHeaders,
    };
    // Never hard-code `web`: the server derives `via` from the token
    // (controller support sessions must stay `via=controller`). A client that
    // wants to identify itself (e.g. the mobile app) opts in explicitly.
    if (options.clientVia) headers["X-Client-Via"] = options.clientVia;
    const token = options.getToken?.();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined && !formBody) headers["Content-Type"] = "application/json";
    const response = await doFetch(`${baseUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : formBody ? (body as FormData) : JSON.stringify(body),
    });
    if (!response.ok) {
      let payload: ApiError | undefined;
      try {
        payload = (await response.json()) as ApiError;
      } catch {
        payload = undefined;
      }
      if (response.status === 401) options.onUnauthorized?.();
      throw new ApiRequestError(
        response.status,
        payload?.error.code ?? "HTTP_ERROR",
        payload?.error.message ?? response.statusText,
        payload?.error.request_id,
        payload?.error.details,
      );
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  return {
    get: <T>(path: string) => request<T>("GET", path),
    post: <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
      request<T>("POST", path, body, headers),
    put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
    patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
    del: <T>(path: string) => request<T>("DELETE", path),
    // Multipart uploads must not set Content-Type: the browser adds the
    // boundary for the FormData body.
    postForm: <T>(path: string, form: FormData) => request<T>("POST", path, form, undefined, true),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
