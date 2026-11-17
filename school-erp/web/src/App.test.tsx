import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "./App";

const messages: Record<string, string> = {
  "app.name": "School ERP",
  "app.tagline": "Manage your school with clarity",
  "nav.dashboard": "Dashboard",
  "auth.email": "Email",
  "auth.password": "Password",
  "auth.sign_in": "Sign in",
  "auth.signing_in": "Signing in…",
  "auth.logout": "Sign out",
  "dashboard.title": "Dashboard",
  "dashboard.welcome": "Welcome, {{name}}",
  "dashboard.subtitle": "This is the walking skeleton.",
  "dashboard.modules": "Enabled modules",
  "dashboard.language_hint": "Language",
  "common.language": "Language",
  "common.theme": "Theme",
  "common.theme.light": "Light",
  "common.theme.dark": "Dark",
  "common.loading": "Loading…",
  "common.not_found": "Page not found",
  "ai.title": "Assistant",
  "sample.title": "Sample module",
  "sample.nav": "Sample module",
};

function json(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
    headers: { get: () => null },
  } as unknown as Response;
}

function renderAt(path: string) {
  return render(
    <AppProviders initialMessages={messages}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("school web shell", () => {
  it("renders the login screen for anonymous users", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    renderAt("/");

    expect(await screen.findByRole("heading", { name: "School ERP" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("renders the authenticated dashboard from the navigation endpoint", async () => {
    localStorage.setItem("erp.access_token", "test-access-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/me")) {
          return json({
            id: "1",
            email: "superadmin@demo.school",
            display_name: "Test User",
            locale: "en",
            roles: ["Super Admin"],
            permissions: ["sample.notes.view"],
            is_controller: false,
          });
        }
        if (url.endsWith("/api/v1/auth/me/navigation")) {
          return json({
            items: [
              { key: "dashboard", label_key: "nav.dashboard", path: "/", module: "core" },
              { key: "sample", label_key: "sample.nav", path: "/sample", module: "sample" },
            ],
            modules: ["sample"],
            locale: "en",
            languages: ["en", "am"],
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    renderAt("/");

    expect(await screen.findByText("Welcome, Test User")).toBeInTheDocument();
    const sidebar = await screen.findByRole("navigation");
    expect(within(sidebar).getByRole("link", { name: "Sample module" })).toHaveAttribute(
      "href",
      "/sample",
    );
  });
});
