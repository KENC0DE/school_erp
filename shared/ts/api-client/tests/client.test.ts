import { describe, expect, it, vi } from "vitest";

import { ApiRequestError, createApiClient } from "../src";

describe("api client", () => {
  it("adds the bearer token and parses json", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const client = createApiClient({
      baseUrl: "http://localhost:8000/",
      getToken: () => "abc",
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    const result = await client.get<{ ok: boolean }>("/api/v1/system/info");
    expect(result.ok).toBe(true);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/system/info");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer abc");
    // `via` is derived from the token server-side so controller sessions are not
    // relabelled as web traffic.
    expect((init.headers as Record<string, string>)["X-Client-Via"]).toBeUndefined();
  });

  it("sends X-Client-Via only when the caller opts in", async () => {
    const fetchImpl = vi.fn(async () => new Response("{}", { status: 200 }));
    const client = createApiClient({
      baseUrl: "http://localhost:8000",
      clientVia: "mobile",
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    await client.get("/api/v1/system/info");
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Client-Via"]).toBe("mobile");
  });

  it("turns the standard error body into an exception", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "MODULE_DISABLED",
              message_key: "error.module_disabled",
              message: "Module is off",
              details: { module: "sample" },
              request_id: "req_1",
            },
          }),
          { status: 403 },
        ),
    );
    const client = createApiClient({
      baseUrl: "http://localhost:8000",
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    await expect(client.get("/api/v1/sample/notes")).rejects.toMatchObject({
      status: 403,
      code: "MODULE_DISABLED",
      requestId: "req_1",
    });
    await expect(client.get("/api/v1/sample/notes")).rejects.toBeInstanceOf(ApiRequestError);
  });
});
