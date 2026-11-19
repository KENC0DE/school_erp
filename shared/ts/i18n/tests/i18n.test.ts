import { describe, expect, it, vi } from "vitest";

import { TranslationLoader, interpolate, translator } from "../src";

describe("i18n runtime loader", () => {
  it("loads, caches and respects ETag", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ locale: "en", namespace: "core", messages: { "app.name": "School ERP" } }), {
          status: 200,
          headers: { etag: 'W/"abc"' },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 304 }));
    const loader = new TranslationLoader({ baseUrl: "http://localhost:8000", fetcher });
    const first = await loader.load("en", "core");
    expect(first.messages["app.name"]).toBe("School ERP");
    const second = await loader.load("en", "core");
    expect(second.messages["app.name"]).toBe("School ERP");
    const [, init] = fetcher.mock.calls[1] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>)["If-None-Match"]).toBe('W/"abc"');
  });

  it("picks up an edited translation without a redeploy", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            locale: "am",
            namespace: "core",
            messages: { "nav.dashboard": "ዳሽቦርድ" },
          }),
          { status: 200, headers: { etag: 'W/"v1"' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            locale: "am",
            namespace: "core",
            messages: { "nav.dashboard": "ዋና ገጽ" },
          }),
          { status: 200, headers: { etag: 'W/"v2"' } },
        ),
      );
    const loader = new TranslationLoader({ baseUrl: "http://localhost:8000", fetcher });
    expect((await loader.load("am", "core")).messages["nav.dashboard"]).toBe("ዳሽቦርድ");
    // The editor write changes the ETag, so the same loader instance fetches the
    // new bundle on the next load instead of keeping the stale cache.
    expect((await loader.load("am", "core")).messages["nav.dashboard"]).toBe("ዋና ገጽ");
    const [, init] = fetcher.mock.calls[1] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>)["If-None-Match"]).toBe('W/"v1"');
  });

  it("keeps other bundles when one namespace is unavailable", async () => {
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/sample")) return new Response(null, { status: 403 });
      return new Response(
        JSON.stringify({ locale: "en", namespace: "core", messages: { "app.name": "School ERP" } }),
        { status: 200 },
      );
    });
    const loader = new TranslationLoader({ baseUrl: "http://localhost:8000", fetcher: fetcher as typeof fetch });
    const messages = await loader.loadMany("en", ["core", "sample"]);
    expect(messages["app.name"]).toBe("School ERP");
  });

  it("prefixes module bundles so manifest keys resolve", async () => {
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      const namespace = url.endsWith("/academics") ? "academics" : "core";
      const messages =
        namespace === "academics" ? { nav: "Academics", "perm.view": "View" } : { "app.name": "School ERP" };
      return new Response(JSON.stringify({ locale: "en", namespace, messages }), { status: 200 });
    });
    const loader = new TranslationLoader({ baseUrl: "http://localhost:8000", fetcher: fetcher as typeof fetch });
    const messages = await loader.loadMany("en", ["core", "academics"]);
    expect(messages["app.name"]).toBe("School ERP");
    expect(messages["academics.nav"]).toBe("Academics");
    expect(messages["academics.perm.view"]).toBe("View");
    expect(messages["nav"]).toBeUndefined();
  });

  it("interpolates named values and keeps unknown placeholders", () => {
    expect(interpolate("Welcome, {{name}}", { name: "Abebe" })).toBe("Welcome, Abebe");
    expect(interpolate("Hello {{missing}}")).toBe("Hello {{missing}}");
  });

  it("translator falls back to the key", () => {
    const t = translator({ "app.name": "School ERP" });
    expect(t("app.name")).toBe("School ERP");
    expect(t("unknown.key")).toBe("unknown.key");
  });
});
