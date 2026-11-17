import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "../App";

const messages: Record<string, string> = {
  "app.name": "School ERP",
  "app.short_name": "SE",
  "nav.dashboard": "Dashboard",
  "nav.themes": "Themes",
  "settings.enum.en": "English",
  "settings.enum.am": "Amharic",
  "common.loading": "Loading…",
  "common.error": "Something went wrong",
  "common.language": "Language",
  "common.theme": "Theme",
  "common.theme.light": "Light",
  "common.theme.dark": "Dark",
  "auth.logout": "Sign out",
  "error.permission_denied": "You do not have permission to do that.",
  "themes.title": "Theme Manager",
  "themes.description": "Import and validate themes.",
  "themes.list": "Themes",
  "themes.list_hint": "The school default is used by everyone.",
  "themes.import": "Import a theme",
  "themes.import_hint": "Paste CSS, upload JSON or paste a registry URL.",
  "themes.format": "Format",
  "themes.format.css": "CSS variables",
  "themes.format.json": "JSON",
  "themes.format.registry": "Registry URL",
  "themes.name": "Theme name",
  "themes.key": "Key",
  "themes.description_field": "Description",
  "themes.content": "CSS or JSON",
  "themes.registry_url": "Registry URL",
  "themes.content_placeholder": "Paste CSS",
  "themes.choose_file": "Choose a JSON or CSS file",
  "themes.preview": "Preview",
  "themes.save": "Save theme",
  "themes.saved": "Theme saved",
  "themes.valid": "Valid",
  "themes.invalid": "Not valid",
  "themes.fallback": "The app falls back to {{name}}.",
  "themes.issues": "Problems found",
  "themes.contrast": "Contrast checks",
  "themes.mode": "Mode",
  "themes.mode.light": "Light",
  "themes.mode.dark": "Dark",
  "themes.pair": "Text / background",
  "themes.ratio": "Ratio",
  "themes.result": "Result",
  "themes.pass": "Pass",
  "themes.fail": "Fail",
  "themes.default": "School default",
  "themes.available": "Available",
  "themes.hidden": "Hidden",
  "themes.broken": "Broken",
  "themes.source": "Source",
  "themes.actions": "Actions",
  "themes.set_default": "Set default",
  "themes.activate": "Make available",
  "themes.deactivate": "Hide",
  "themes.delete": "Delete",
  "themes.delete_confirm": "Delete the theme {{name}}?",
  "themes.detail": "Theme preview",
  "themes.detail_hint": "Preview both modes.",
  "themes.close": "Close",
  "themes.loading": "Loading themes…",
  "themes.no_items": "No themes have been imported yet.",
  "themes.sample_heading": "Sample heading",
  "themes.sample_body": "Body text shows the contrast of this theme.",
  "themes.sample_button": "Sample button",
  "themes.school_default": "School default",
  "themes.choice": "Your theme",
  "themes.status": "Status",
};

interface ThemeRow {
  key: string;
  name: string;
  description: string | null;
  is_default: boolean;
  is_active: boolean;
  is_builtin: boolean;
  source: string;
  source_url: string | null;
  row_version: number;
  valid: boolean;
  tokens: { light: Record<string, string>; dark: Record<string, string> };
}

let themes: ThemeRow[] = [];
let requests: { method: string; url: string; body: unknown }[] = [];
let mePermissions: string[] = ["*"];
let preference: { theme_key: string | null; mode: string } = { theme_key: null, mode: "light" };

const LIGHT = {
  background: "#ffffff",
  foreground: "#111111",
  primary: "#006600",
  "primary-foreground": "#ffffff",
  muted: "#eeeeee",
  accent: "#ffeeaa",
  sidebar: "#f5f5f5",
};

const DARK = {
  background: "#111111",
  foreground: "#eeeeee",
  primary: "#33aa33",
  "primary-foreground": "#111111",
  muted: "#333333",
  accent: "#554400",
  sidebar: "#1a1a1a",
};

const CONTRAST = [
  {
    mode: "light" as const,
    foreground_token: "background",
    background_token: "foreground",
    foreground: "#ffffff",
    background: "#111111",
    ratio: 18.5,
    minimum: 4.5,
    passes: true,
    message: "Light theme is readable.",
  },
  {
    mode: "dark" as const,
    foreground_token: "background",
    background_token: "foreground",
    foreground: "#111111",
    background: "#eeeeee",
    ratio: 16.2,
    minimum: 4.5,
    passes: true,
    message: "Dark theme is readable.",
  },
];

function theme(
  key: string,
  name: string,
  overrides: Partial<ThemeRow> = {},
): ThemeRow {
  return {
    key,
    name,
    description: null,
    is_default: key === "default",
    is_active: true,
    is_builtin: key === "default",
    source: key === "default" ? "builtin" : "json",
    source_url: null,
    row_version: 1,
    valid: true,
    tokens: { light: LIGHT, dark: DARK },
    ...overrides,
  };
}

function resetStore() {
  themes = [theme("default", "Default"), theme("ocean", "Ocean", { description: "Blue" })];
  requests = [];
  mePermissions = ["*"];
  preference = { theme_key: null, mode: "light" };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function detailOf(row: ThemeRow) {
  return {
    ...row,
    issues: [],
    contrast: CONTRAST,
    css: { light: "--background: #ffffff;", dark: "--background: #111111;" },
    mobile: { light: { colors: {} }, dark: { colors: {} } },
  };
}

function previewOf(body: { name?: string | null; key?: string | null; content: string }) {
  const bad = body.content.includes("BAD_CONTRAST");
  const key = body.key || "ocean-preview";
  const name = body.name || "Ocean preview";
  const issues = bad
    ? [
        {
          code: "contrast",
          mode: "light",
          message:
            "Light theme: '#ffffff' on '#ffffff' has a contrast ratio of 1.00:1; it must be at least 4.5:1.",
        },
      ]
    : [];
  return {
    valid: !bad,
    key,
    name,
    source: "json",
    issues,
    contrast: CONTRAST,
    tokens: { light: LIGHT, dark: DARK },
    css: { light: "--background: #ffffff;", dark: "--background: #111111;" },
    mobile: { light: { colors: {} }, dark: { colors: {} } },
    warnings: [],
    fallback: bad ? { key: "default", name: "Default" } : null,
  };
}

async function stubFetch(input: RequestInfo | URL, init?: RequestInit) {
  const url = new URL(String(input), "http://localhost:8000");
  const method = init?.method ?? "GET";
  const body = init?.body ? JSON.parse(String(init.body)) : undefined;
  requests.push({ method, url: url.pathname + url.search, body });

  if (url.pathname === "/api/v1/auth/me") {
    return json({
      id: "u-admin",
      email: "superadmin@demo.school",
      display_name: "Super Admin",
      locale: "en",
      roles: ["super_admin"],
      permissions: mePermissions,
      is_controller: false,
    });
  }
  if (url.pathname === "/api/v1/auth/me/navigation") {
    return json({
      items: [
        { key: "dashboard", label_key: "nav.dashboard", path: "/", module: "core" },
        { key: "themes", label_key: "nav.themes", path: "/settings/themes", module: "core" },
      ],
      modules: [],
      locale: "en",
      languages: ["en", "am"],
    });
  }
  if (url.pathname === "/api/v1/themes/active") {
    const chosen = preference.theme_key
      ? themes.find((row) => row.key === preference.theme_key)
      : undefined;
    const active = chosen ?? themes.find((row) => row.is_default) ?? themes[0];
    return json({
      key: active.key,
      name: active.name,
      tokens: active.tokens,
      source: chosen ? "user" : "instance",
      mode: preference.mode,
      user_theme_key: preference.theme_key,
      fallback: false,
      reason: [],
    });
  }
  if (url.pathname === "/api/v1/themes/available") {
    return json({ items: themes.filter((row) => row.is_active) });
  }
  if (url.pathname === "/api/v1/themes/preview" && method === "POST") {
    return json(previewOf(body));
  }
  if (url.pathname === "/api/v1/themes/import" && method === "POST") {
    if (body.content.includes("BAD_CONTRAST")) {
      return json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message_key: "error.theme.invalid",
            message: "The theme did not pass validation",
            details: { issues: previewOf(body).issues },
            request_id: "req-1",
          },
        },
        422,
      );
    }
    const created = theme(body.key || "ocean-preview", body.name || "Ocean preview", {
      description: body.description,
      source: "css",
    });
    themes.push(created);
    return json(detailOf(created), 201);
  }
  if (url.pathname.endsWith("/default") && method === "POST") {
    const key = url.pathname.split("/")[4];
    themes = themes.map((row) => ({ ...row, is_default: row.key === key, row_version: row.row_version + 1 }));
    return json(detailOf(themes.find((row) => row.key === key)!));
  }
  if (url.pathname.startsWith("/api/v1/themes/") && method === "PATCH") {
    const key = url.pathname.split("/")[4];
    const row = themes.find((item) => item.key === key);
    if (!row) return json({ error: { code: "NOT_FOUND" } }, 404);
    Object.assign(row, { is_active: body.is_active, row_version: row.row_version + 1 });
    return json(detailOf(row));
  }
  if (url.pathname.startsWith("/api/v1/themes/") && method === "DELETE") {
    const key = url.pathname.split("/")[4];
    themes = themes.filter((row) => row.key !== key);
    return json({ key, deleted: true });
  }
  if (url.pathname === "/api/v1/themes" && method === "GET") {
    return json({ items: themes });
  }
  if (url.pathname.startsWith("/api/v1/themes/") && method === "GET") {
    const key = url.pathname.split("/")[4];
    const row = themes.find((item) => item.key === key);
    return row ? json(detailOf(row)) : json({ error: { code: "NOT_FOUND" } }, 404);
  }
  if (url.pathname === "/api/v1/themes/preference" && method === "PUT") {
    preference = { theme_key: body.theme_key, mode: body.mode };
    return json({ theme_key: body.theme_key, theme_mode: body.mode, theme: {} });
  }
  return json({ error: { code: "NOT_FOUND", message: url.pathname } }, 404);
}

function renderAt(path: string) {
  return render(
    <AppProviders
      initialMessages={messages}
      queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-token");
  resetStore();
  vi.stubGlobal("fetch", vi.fn(stubFetch));
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ThemeManagerPage", () => {
  it("lists themes and previews both modes and contrast", async () => {
    renderAt("/settings/themes");

    const row = await screen.findByTestId("theme-row-ocean");
    expect(within(row).getByText("Ocean")).toBeInTheDocument();
    expect(within(row).getByText("Available")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("theme-row-default")).getByText("School default"),
    ).toBeInTheDocument();

    fireEvent.click(within(row).getByTestId("theme-preview-row-ocean"));
    expect(await screen.findByTestId("theme-preview")).toBeInTheDocument();
    expect(screen.getAllByTestId("theme-contrast-table").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Light").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dark").length).toBeGreaterThan(0);
  });

  it("rejects an unreadable pair with the backend reason before saving", async () => {
    renderAt("/settings/themes");
    await screen.findByTestId("theme-row-ocean");

    fireEvent.change(screen.getByTestId("theme-content"), {
      target: { value: "BAD_CONTRAST" },
    });
    fireEvent.click(screen.getByTestId("theme-preview-button"));

    const issues = await screen.findByTestId("theme-issues");
    expect(issues).toHaveTextContent("Problems found");
    expect(issues).toHaveTextContent("contrast ratio of 1.00:1");
    expect(screen.getByText("Not valid")).toBeInTheDocument();
    expect(screen.getByTestId("theme-save-button")).toBeDisabled();
    expect(requests.some((request) => request.url === "/api/v1/themes/import")).toBe(false);
  });

  it("previews then imports a valid theme", async () => {
    renderAt("/settings/themes");
    await screen.findByTestId("theme-row-ocean");

    fireEvent.change(screen.getByTestId("theme-name"), { target: { value: "Sunrise" } });
    fireEvent.change(screen.getByTestId("theme-key"), { target: { value: "sunrise" } });
    fireEvent.change(screen.getByTestId("theme-content"), {
      target: { value: ":root { --background: #ffffff; }" },
    });
    fireEvent.click(screen.getByTestId("theme-preview-button"));
    await screen.findByText("Valid");
    fireEvent.click(screen.getByTestId("theme-save-button"));

    await waitFor(() => expect(screen.getByTestId("theme-row-sunrise")).toBeInTheDocument());
    const post = requests.find((request) => request.url === "/api/v1/themes/import");
    expect(post?.body).toMatchObject({
      format: "css",
      name: "Sunrise",
      key: "sunrise",
    });
    expect(screen.getByText("Theme saved")).toBeInTheDocument();
  });

  it("sets the school default, hides and deletes a theme", async () => {
    renderAt("/settings/themes");
    const row = await screen.findByTestId("theme-row-ocean");

    fireEvent.click(within(row).getByTestId("theme-default-ocean"));
    await waitFor(() => expect(themes.find((item) => item.key === "ocean")?.is_default).toBe(true));

    const updated = await screen.findByTestId("theme-row-ocean");
    fireEvent.click(within(updated).getByTestId("theme-toggle-ocean"));
    await waitFor(() => expect(themes.find((item) => item.key === "ocean")?.is_active).toBe(false));
    expect(await screen.findByText("Hidden")).toBeInTheDocument();

    const hidden = await screen.findByTestId("theme-row-ocean");
    fireEvent.click(within(hidden).getByTestId("theme-delete-ocean"));
    await waitFor(() =>
      expect(screen.queryByTestId("theme-row-ocean")).not.toBeInTheDocument(),
    );
    expect(window.confirm).toHaveBeenCalled();
    expect(screen.queryByTestId("theme-delete-default")).not.toBeInTheDocument();
  });

  it("explains when the user cannot manage themes", async () => {
    mePermissions = [];
    renderAt("/settings/themes");
    expect(
      await screen.findByText("You do not have permission to do that."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("theme-row-ocean")).not.toBeInTheDocument();
  });

  it("lets a signed-in user pick their own available theme", async () => {
    renderAt("/settings/themes");
    const picker = await screen.findByRole("combobox", { name: "Your theme" });
    fireEvent.change(picker, { target: { value: "ocean" } });

    await waitFor(() =>
      expect(
        requests.some(
          (request) =>
            request.url === "/api/v1/themes/preference" &&
            request.method === "PUT" &&
            (request.body as { theme_key?: string }).theme_key === "ocean",
        ),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Your theme" })).toHaveValue("ocean"),
    );
  });
});
