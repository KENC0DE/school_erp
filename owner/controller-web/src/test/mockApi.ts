import { vi } from "vitest";

export interface MockResult {
  status?: number;
  body?: unknown;
}

export type MockHandler = (url: string, init: RequestInit) => MockResult | Promise<MockResult>;

/** Installs a fetch stub that resolves through `handler` and returns a Response. */
export function installFetch(handler: MockHandler) {
  const mock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url =
      typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const result = await handler(url, init);
    const status = result.status ?? 200;
    return new Response(result.body === undefined ? null : JSON.stringify(result.body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  global.fetch = mock as unknown as typeof fetch;
  return mock;
}

export const OWNER = {
  id: "u1",
  email: "owner@controller.local",
  display_name: "Platform Owner",
  role: "owner",
};

export const SCHOOL = {
  id: "s1",
  name: "Demo Academy",
  school_code: "DEMO",
  api_base_url: "http://localhost:8000",
  logo_url: null,
  status: "active",
  min_app_version: "0.0.0",
  plan: "standard",
  size_profile: "small",
  modules: ["academics", "sample"],
  app_version: "0.1.0",
  enrolled: true,
  created_at: null,
};

export const SECOND_SCHOOL = {
  ...SCHOOL,
  id: "s2",
  name: "Second School",
  school_code: "DEMO2",
  status: "suspended",
  modules: ["fees"],
  enrolled: false,
};

export function handleAuth(url: string): MockResult | null {
  if (url.endsWith("/controller/v1/auth/me")) return { body: OWNER };
  return null;
}

export function notFound(url: string): MockResult {
  return {
    status: 404,
    body: { error: { code: "NOT_FOUND", message: `Unhandled request ${url}` } },
  };
}

export function jsonBody(init: RequestInit): Record<string, unknown> {
  return JSON.parse(String(init.body ?? "{}")) as Record<string, unknown>;
}
