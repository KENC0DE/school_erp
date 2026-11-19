import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "../App";

const messages: Record<string, string> = {
  "app.name": "School ERP",
  "app.short_name": "SE",
  "app.tagline": "Manage your school with clarity",
  "nav.dashboard": "Dashboard",
  "settings.enum.en": "English",
  "settings.enum.am": "Amharic",
  "settings.enum.ethiopian": "Ethiopian",
  "settings.enum.gregorian": "Gregorian",
  "settings.enum.both": "Both",
  "common.loading": "Loading…",
  "common.error": "Something went wrong",
  "common.retry": "Retry",
  "common.language": "Language",
  "common.theme": "Theme",
  "common.theme.light": "Light",
  "common.theme.dark": "Dark",
  "auth.email": "Email",
  "auth.password": "Password",
  "auth.sign_in": "Sign in",
  "auth.signing_in": "Signing in…",
  "auth.logout": "Sign out",
  "files.error.too_large": "This file is larger than the {{max}} MB limit.",
  "setup.title": "Set up your school",
  "setup.intro": "This one-time wizard creates the school profile.",
  "setup.school_section": "School profile",
  "setup.school_name": "School name",
  "setup.timezone": "Time zone",
  "setup.calendar": "Calendar display",
  "setup.default_language": "Default language",
  "setup.enabled_languages": "Enabled languages",
  "setup.enabled_languages_hint": "Separate language codes with commas.",
  "setup.first_level": "First grade level",
  "setup.last_level": "Last grade level",
  "setup.grade_scope_hint": "A placeholder for now.",
  "setup.theme": "School theme",
  "setup.logo": "School logo",
  "setup.logo_hint": "PNG, JPEG or WebP up to {{max}} MB.",
  "setup.logo_remove": "Remove logo",
  "setup.admin_section": "First Super Admin",
  "setup.admin_name": "Full name",
  "setup.admin_email": "Email",
  "setup.admin_password": "Password",
  "setup.admin_password_hint": "At least 12 characters, with a letter and a digit.",
  "setup.admin_phone": "Phone (optional)",
  "setup.submit": "Finish setup",
  "setup.submitting": "Setting up…",
  "setup.loading": "Loading setup…",
  "setup.complete_title": "Setup is already complete",
  "setup.complete_body": "This instance has an account. Sign in to continue.",
  "setup.go_to_login": "Go to sign in",
  "setup.error": "Setup could not be completed.",
  "error.setup_language": "The default language must also be enabled",
  "error.setup_grade_scope": "The first grade level cannot be above the last",
  "error.setup_logo": "The logo must be a PNG, JPEG or WebP image",
  "dashboard.title": "Dashboard",
  "dashboard.welcome": "Welcome, {{name}}",
  "dashboard.subtitle": "This is the walking skeleton.",
  "dashboard.modules": "Enabled modules",
  "dashboard.language_hint": "Language",
};

interface Status {
  required: boolean;
  completed: boolean;
  school: {
    name: string;
    timezone: string;
    calendar: string;
    default_language: string;
    enabled_languages: string[];
    first_level: number;
    last_level: number;
    theme: string;
    logo_url: string | null;
  };
  languages: string[];
  calendars: string[];
  themes: { key: string; name: string; is_default: boolean }[];
  limits: { logo_max_bytes: number };
}

let status: Status;
let posts: Record<string, unknown>[] = [];
let setupResult: unknown;

function json(body: unknown, statusCode = 200): Response {
  return new Response(JSON.stringify(body), {
    status: statusCode,
    headers: { "Content-Type": "application/json" },
  });
}

function statusPayload(overrides: Partial<Status> = {}): Status {
  return {
    required: true,
    completed: false,
    school: {
      name: "Demo Academy",
      timezone: "Africa/Addis_Ababa",
      calendar: "both",
      default_language: "en",
      enabled_languages: ["en", "am"],
      first_level: 0,
      last_level: 12,
      theme: "default",
      logo_url: null,
    },
    languages: ["en", "am"],
    calendars: ["ethiopian", "gregorian", "both"],
    themes: [
      { key: "default", name: "Default", is_default: true },
      { key: "ocean", name: "Ocean", is_default: false },
    ],
    limits: { logo_max_bytes: 1_000_000 },
    ...overrides,
  };
}

function navigation() {
  return {
    items: [{ key: "dashboard", label_key: "nav.dashboard", path: "/", module: "core" }],
    modules: [],
    locale: "en",
    languages: ["en", "am"],
  };
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
  status = statusPayload();
  posts = [];
  setupResult = {
    tokens: {
      access_token: "setup-access",
      refresh_token: "setup-refresh",
      token_type: "bearer",
      expires_in: 900,
    },
    user: {
      id: "u-founder",
      email: "founder@alpha.school",
      display_name: "Alpha Founder",
      locale: "am",
      roles: ["super_admin"],
      permissions: ["*"],
      is_controller: false,
    },
    school: { "school_profile.name": "Alpha Academy" },
    logo_url: null,
    theme: "default",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/setup/status") && method === "GET") return json(status);
      if (url.endsWith("/api/v1/setup") && method === "POST") {
        posts.push(JSON.parse(String(init?.body ?? "{}")));
        return json(setupResult);
      }
      if (url.endsWith("/api/v1/auth/me")) {
        return json((setupResult as { user: unknown }).user);
      }
      if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
      if (url.endsWith("/api/v1/themes/active")) return json({}, 404);
      if (url.endsWith("/api/v1/themes/available")) return json({ items: [] });
      throw new Error(`Unexpected request: ${method} ${url}`);
    }),
  );
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("instance setup wizard", () => {
  it("renders the school and admin sections with server defaults", async () => {
    renderAt("/setup");

    expect(await screen.findByRole("heading", { name: "Set up your school" })).toBeInTheDocument();
    expect(screen.getByLabelText("School name")).toHaveValue("Demo Academy");
    expect(screen.getByLabelText("Time zone")).toHaveValue("Africa/Addis_Ababa");
    expect(screen.getByLabelText("Default language")).toHaveValue("en");
    expect(screen.getByRole("option", { name: "Ocean" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "First Super Admin" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finish setup" })).toBeInTheDocument();
  });

  it("submits the nested payload and adopts the returned session", async () => {
    renderAt("/setup");

    fireEvent.change(await screen.findByLabelText("School name"), {
      target: { value: "Alpha Academy" },
    });
    fireEvent.change(screen.getByLabelText("Full name"), {
      target: { value: "Alpha Founder" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "founder@alpha.school" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "FounderPass#2026" },
    });
    fireEvent.change(screen.getByLabelText("Default language"), {
      target: { value: "am" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Finish setup" }));

    await waitFor(() => expect(posts).toHaveLength(1));
    const body = posts[0] as {
      school: Record<string, unknown>;
      admin: Record<string, unknown>;
    };
    expect(body.school).toMatchObject({
      name: "Alpha Academy",
      timezone: "Africa/Addis_Ababa",
      calendar: "both",
      default_language: "am",
      enabled_languages: ["en", "am"],
      first_level: 0,
      last_level: 12,
      theme: "default",
      logo: null,
    });
    expect(body.admin).toEqual({
      email: "founder@alpha.school",
      password: "FounderPass#2026",
      display_name: "Alpha Founder",
      phone: null,
      locale: "am",
    });

    await waitFor(() => expect(localStorage.getItem("erp.access_token")).toBe("setup-access"));
    expect(localStorage.getItem("erp.refresh_token")).toBe("setup-refresh");
    expect(await screen.findByText("Welcome, Alpha Founder")).toBeInTheDocument();
  });

  it("shows a completed state and links to sign in", async () => {
    status = statusPayload({ required: false, completed: true });
    renderAt("/setup");

    expect(await screen.findByText("Setup is already complete")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to sign in" })).toHaveAttribute("href", "/login");
    expect(screen.queryByTestId("setup-form")).not.toBeInTheDocument();
  });

  it("redirects anonymous visitors from sign in to the wizard", async () => {
    renderAt("/login");

    expect(await screen.findByRole("heading", { name: "Set up your school" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign in" })).not.toBeInTheDocument();
  });

  it("blocks an inverted grade range before calling the API", async () => {
    renderAt("/setup");

    fireEvent.change(await screen.findByLabelText("Full name"), {
      target: { value: "Alpha Founder" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "founder@alpha.school" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "FounderPass#2026" },
    });
    fireEvent.change(screen.getByLabelText("First grade level"), {
      target: { value: "9" },
    });
    fireEvent.change(screen.getByLabelText("Last grade level"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Finish setup" }));

    expect(
      await screen.findByText("The first grade level cannot be above the last"),
    ).toBeInTheDocument();
    expect(posts).toHaveLength(0);
  });

  it("previews a chosen logo and rejects a wrong file type", async () => {
    renderAt("/setup");
    const input = await screen.findByLabelText("School logo");

    const image = new File([new Uint8Array([137, 80, 78, 71])], "logo.png", {
      type: "image/png",
    });
    fireEvent.change(input, { target: { files: [image] } });
    expect(await screen.findByRole("img", { name: "School logo" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Remove logo" }));
    const text = new File(["hello"], "logo.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [text] } });
    expect(await screen.findByText("The logo must be a PNG, JPEG or WebP image")).toBeInTheDocument();
  });
});
