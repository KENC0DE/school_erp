import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  "settings.title": "Settings",
  "settings.intro": "Layered settings",
  "settings.module.core": "School",
  "settings.core.school_profile.name": "School name",
  "settings.save": "Save",
  "settings.reset": "Reset to default",
  "settings.source.code": "Code default",
  "settings.source.central": "Central",
  "settings.source.instance": "School",
  "nav.settings": "Settings",
  "auth.reset_password": "Choose a new password",
  "auth.reset_password_hint": "Use the single-use link from your invitation or reset email.",
  "auth.new_password": "New password",
  "auth.confirm_password": "Confirm password",
  "auth.passwords_mismatch": "The two passwords do not match",
  "auth.reset_password_submit": "Set password",
  "auth.reset_password_success": "Your password has been changed. You can sign in now.",
  "auth.back_to_sign_in": "Back to sign in",
  "error.invalid_reset_token": "This reset link is invalid or has expired",
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

  it("sets a new password from the emailed link", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/reset-password") && init?.method === "POST") {
        return json({ ok: true });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/reset-password?token=single-use-token");

    fireEvent.change(await screen.findByLabelText("New password"), {
      target: { value: "AnotherPass#2026" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "AnotherPass#2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/api/v1/auth/reset-password") && init?.method === "POST",
      );
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({
        token: "single-use-token",
        new_password: "AnotherPass#2026",
      });
    });
    expect(
      await screen.findByText("Your password has been changed. You can sign in now."),
    ).toBeInTheDocument();
  });

  it("renders generated settings and saves a value", async () => {
    localStorage.setItem("erp.access_token", "test-access-token");
    const field = {
      module: "core",
      key: "school_profile.name",
      type: "string",
      default: "Demo Academy",
      label_key: "settings.core.school_profile.name",
      enum: null,
      minimum: null,
      maximum: null,
      max_length: 200,
      secret: false,
      value: "Demo Academy",
      source: "code",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/auth/me")) {
        return json({
          id: "1",
          email: "superadmin@demo.school",
          display_name: "Test User",
          locale: "en",
          roles: ["Super Admin"],
          permissions: ["settings.view", "settings.manage"],
          is_controller: false,
        });
      }
      if (url.endsWith("/api/v1/auth/me/navigation")) {
        return json({
          items: [
            { key: "dashboard", label_key: "nav.dashboard", path: "/", module: "core" },
            { key: "settings", label_key: "nav.settings", path: "/settings", module: "core" },
          ],
          modules: [],
          locale: "en",
          languages: ["en", "am"],
        });
      }
      if (url.endsWith("/api/v1/settings") && method === "GET") {
        return json({
          items: [{ module: "core", label_key: "settings.module.core", fields: [field] }],
          next_cursor: null,
        });
      }
      if (url.endsWith("/api/v1/settings/core/school_profile.name") && method === "PUT") {
        return json({ ...field, value: "Renamed", source: "instance" });
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/settings");

    const input = await screen.findByLabelText("School name");
    expect(input).toHaveValue("Demo Academy");
    expect(screen.getByText("Code default")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/api/v1/settings/core/school_profile.name") &&
          init?.method === "PUT",
      );
      expect(call).toBeTruthy();
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({ value: "Renamed" });
    });
  });
});
