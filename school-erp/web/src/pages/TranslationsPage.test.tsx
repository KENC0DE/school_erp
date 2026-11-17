import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "../App";

const messages: Record<string, string> = {
  "app.name": "School ERP",
  "nav.dashboard": "Dashboard",
  "nav.languages": "Languages",
  "nav.settings": "Settings",
  "common.loading": "Loading…",
  "common.error": "Something went wrong",
  "common.language": "Language",
  "common.theme": "Theme",
  "common.theme.light": "Light",
  "common.theme.dark": "Dark",
  "auth.logout": "Sign out",
  "error.permission_denied": "You do not have permission to do that.",
  "translations.title": "Translation editor",
  "translations.description": "Edit the labels people see.",
  "translations.search": "Search keys and text",
  "translations.module": "Module",
  "translations.all_modules": "All modules",
  "translations.status": "Status",
  "translations.all_statuses": "All statuses",
  "translations.missing": "Missing",
  "translations.needs_review": "Needs review",
  "translations.approved": "Approved",
  "translations.layer": "Layer",
  "translations.all_layers": "All layers",
  "translations.layer.school": "School override",
  "translations.layer.central": "Central",
  "translations.layer.default": "Default",
  "translations.apply": "Apply filters",
  "translations.clear": "Clear",
  "translations.key": "Key",
  "translations.source": "English source",
  "translations.target": "Translation",
  "translations.save": "Save",
  "translations.saved": "Saved",
  "translations.reset": "Reset to default",
  "translations.empty": "No labels match these filters.",
  "translations.loading": "Loading labels…",
  "translations.total": "{{count}} labels",
  "translations.missing_count": "{{count}} missing",
  "translations.review_count": "{{count}} need review",
  "translations.overrides_count": "{{count}} school overrides",
  "translations.permission_denied": "You do not have permission to edit translations.",
  "translations.import": "Import",
  "translations.import_hint": "Paste CSV or JSON.",
  "translations.import_button": "Import translations",
  "translations.import_summary": "{{imported}} updated, {{unchanged}} unchanged",
  "translations.export_json": "Export JSON",
  "translations.export_csv": "Export CSV",
  "translations.in_context": "In-context preview",
  "translations.in_context_hint": "Click any label to edit its translation.",
  "translations.table_mode": "Back to the table",
  "translations.choose_key": "Choose a label to edit",
};

interface Row {
  namespace: string;
  key: string;
  source: string;
  value: string;
  status: string;
  source_kind: string | null;
  layer: string | null;
  updated_at: string | null;
}

let store: Row[] = [];
let requests: { method: string; url: string; body: unknown }[] = [];
let mePermissions: string[] = ["*"];

function resetStore() {
  store = [
    {
      namespace: "core",
      key: "nav.dashboard",
      source: "Dashboard",
      value: "ዳሽቦርድ",
      status: "approved",
      source_kind: "human",
      layer: "default",
      updated_at: "2026-01-01T00:00:00Z",
    },
    {
      namespace: "core",
      key: "nav.welcome",
      source: "Welcome",
      value: "",
      status: "missing",
      source_kind: null,
      layer: null,
      updated_at: null,
    },
    {
      namespace: "core",
      key: "common.cancel",
      source: "Cancel",
      value: "ሰርዝ",
      status: "needs_review",
      source_kind: "ai",
      layer: "central",
      updated_at: "2026-01-02T00:00:00Z",
    },
  ];
  requests = [];
  mePermissions = ["*"];
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function statsFor(namespace: string | null) {
  const rows = store.filter((row) => !namespace || row.namespace === namespace);
  return {
    total: rows.length,
    missing: rows.filter((row) => row.status === "missing").length,
    needs_review: rows.filter((row) => row.status === "needs_review").length,
    overrides: rows.filter((row) => row.layer === "school").length,
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
        { key: "languages", label_key: "nav.languages", path: "/settings/languages", module: "core" },
      ],
      modules: [],
      locale: "en",
      languages: ["en", "am"],
    });
  }
  if (url.pathname === "/api/v1/i18n/editor/namespaces") {
    return json({ items: ["core", "sample"] });
  }
  if (url.pathname === "/api/v1/i18n/editor/stats") {
    return json(statsFor(url.searchParams.get("namespace")));
  }
  if (url.pathname === "/api/v1/i18n/editor/entries" && method === "GET") {
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    const status = url.searchParams.get("status");
    const layer = url.searchParams.get("layer");
    const namespace = url.searchParams.get("namespace");
    const items = store.filter(
      (row) =>
        (!namespace || row.namespace === namespace) &&
        (!status || row.status === status) &&
        (!layer || row.layer === layer) &&
        (!q ||
          row.key.toLowerCase().includes(q) ||
          row.source.toLowerCase().includes(q) ||
          row.value.toLowerCase().includes(q)),
    );
    return json({ items, total: items.length, next_cursor: null });
  }
  if (url.pathname.startsWith("/api/v1/i18n/editor/entries/") && method === "PUT") {
    const [, , , , , , namespace, key, locale] = url.pathname.split("/");
    const row = store.find((item) => item.namespace === namespace && item.key === key);
    if (!row || locale !== "am") return json({ error: { code: "NOT_FOUND" } }, 404);
    row.value = body.value;
    row.status = body.status;
    row.layer = "school";
    row.source_kind = "human";
    return json(row);
  }
  if (url.pathname.endsWith("/reset") && method === "POST") {
    const parts = url.pathname.split("/");
    const namespace = parts[6];
    const key = parts[7];
    const row = store.find((item) => item.namespace === namespace && item.key === key);
    if (!row || row.layer !== "school") return json({ error: { code: "NOT_FOUND" } }, 404);
    row.value = row.key === "nav.dashboard" ? "ዳሽቦርድ" : "";
    row.status = row.key === "nav.dashboard" ? "approved" : "missing";
    row.layer = "default";
    return json(row);
  }
  if (url.pathname === "/api/v1/i18n/editor/import") {
    return json({ imported: 2, unchanged: 1 });
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
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("TranslationsPage", () => {
  it("lists keys with source, translation, layer and status, and filters them", async () => {
    renderAt("/settings/languages");

    const row = await screen.findByTestId("translation-row-core-nav.dashboard");
    expect(within(row).getByText("Dashboard")).toBeInTheDocument();
    expect(within(row).getByTestId("translation-input-nav.dashboard")).toHaveValue("ዳሽቦርድ");
    expect(within(row).getByTestId("translation-layer-nav.dashboard")).toHaveTextContent("Default");
    expect(within(row).getByTestId("translation-status-nav.dashboard")).toHaveTextContent("Approved");
    expect(screen.getByText("3 labels")).toBeInTheDocument();
    expect(screen.getByText("1 missing")).toBeInTheDocument();
    expect(screen.getByText("1 need review")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search keys and text"), {
      target: { value: "welcome" },
    });
    fireEvent.click(screen.getByTestId("translations-apply"));

    await waitFor(() =>
      expect(requests.some((request) => request.url.includes("q=welcome"))).toBe(true),
    );
    await waitFor(() =>
      expect(screen.queryByTestId("translation-row-core-nav.dashboard")).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId("translation-row-core-nav.welcome")).toBeInTheDocument();
  });

  it("edits a translation inline and stores a school override", async () => {
    renderAt("/settings/languages");

    const row = await screen.findByTestId("translation-row-core-nav.dashboard");
    fireEvent.change(within(row).getByTestId("translation-input-nav.dashboard"), {
      target: { value: "ዋና ገጽ" },
    });
    fireEvent.click(within(row).getByTestId("translation-save-nav.dashboard"));

    await waitFor(() =>
      expect(
        requests.some(
          (request) =>
            request.method === "PUT" &&
            request.url === "/api/v1/i18n/editor/entries/core/nav.dashboard/am",
        ),
      ).toBe(true),
    );
    const put = requests.find((request) => request.method === "PUT");
    expect(put?.body).toEqual({ value: "ዋና ገጽ", status: "approved" });
    await waitFor(() => expect(store[0].value).toBe("ዋና ገጽ"));
    expect(store[0].layer).toBe("school");
    await waitFor(() =>
      expect(screen.getByTestId("translation-layer-nav.dashboard")).toHaveTextContent(
        "School override",
      ),
    );
    expect(screen.getByTestId("translation-reset-nav.dashboard")).toBeInTheDocument();
  });

  it("offers in-context editing of a visible label", async () => {
    renderAt("/settings/languages");
    await screen.findByTestId("translation-row-core-nav.dashboard");

    fireEvent.click(screen.getByTestId("translations-toggle-preview"));
    expect(screen.getByTestId("in-context-preview")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("translation-preview-core-nav.dashboard"));

    const input = await screen.findByTestId("translation-input-preview-nav.dashboard");
    expect(input).toHaveValue("ዳሽቦርድ");
    fireEvent.change(input, { target: { value: "መጀመሪያ ገጽ" } });
    fireEvent.click(screen.getByTestId("translation-save-preview-nav.dashboard"));
    await waitFor(() => expect(store[0].value).toBe("መጀመሪያ ገጽ"));
  });

  it("imports a JSON batch and reports the summary", async () => {
    renderAt("/settings/languages");
    await screen.findByTestId("translation-row-core-nav.dashboard");

    fireEvent.change(screen.getByTestId("translation-import-content"), {
      target: { value: '{"nav.dashboard":"ዋና ገጽ","nav.welcome":"እንኳን ደህና መጡ"}' },
    });
    fireEvent.click(screen.getByTestId("translation-import-button"));

    await waitFor(() =>
      expect(screen.getByTestId("translation-import-summary")).toHaveTextContent(
        "2 updated, 1 unchanged",
      ),
    );
    const post = requests.find((request) => request.url === "/api/v1/i18n/editor/import");
    expect(post?.body).toEqual({
      namespace: "core",
      locale: "am",
      format: "json",
      content: '{"nav.dashboard":"ዋና ገጽ","nav.welcome":"እንኳን ደህና መጡ"}',
      status: "approved",
    });
    expect(screen.getByTestId("translations-export-json")).toBeInTheDocument();
    expect(screen.getByTestId("translations-export-csv")).toBeInTheDocument();
  });

  it("explains when the user cannot view translations", async () => {
    mePermissions = [];
    renderAt("/settings/languages");
    expect(
      await screen.findByText("You do not have permission to edit translations."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("translation-row-core-nav.dashboard")).not.toBeInTheDocument();
  });
});
