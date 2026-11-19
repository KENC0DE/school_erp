import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "../App";

const messages: Record<string, string> = {
  "app.name": "School ERP",
  "nav.dashboard": "Dashboard",
  "nav.settings": "Settings",
  "nav.modules": "Modules",
  "nav.activity": "Activity history",
  "common.loading": "Loading…",
  "common.error": "Something went wrong",
  "common.cancel": "Cancel",
  "common.language": "Language",
  "common.theme": "Theme",
  "common.theme.light": "Light",
  "common.theme.dark": "Dark",
  "error.permission_denied": "You do not have permission to do that.",
  "settings.module.sample": "Sample module",
  "activity.title": "Activity history",
  "activity.intro": "Who changed what, with before and after values.",
  "activity.filters": "Filters",
  "activity.user": "User",
  "activity.module": "Module",
  "activity.entity_type": "Entity type",
  "activity.entity_id": "Entity ID",
  "activity.action": "Action",
  "activity.date_from": "From",
  "activity.date_to": "To",
  "activity.apply": "Apply filters",
  "activity.clear": "Clear",
  "activity.all_users": "All users",
  "activity.all_modules": "All modules",
  "activity.all_actions": "All actions",
  "activity.empty": "No activity matches these filters.",
  "activity.controller": "Controller",
  "activity.system": "System",
  "activity.on_behalf_of": "On behalf of",
  "activity.reason": "Reason",
  "activity.changes": "Changes",
  "activity.field": "Field",
  "activity.no_changes": "No value changes",
  "activity.before": "Before",
  "activity.after": "After",
  "activity.permission_denied": "You do not have permission to view the activity history.",
  "activity.loading": "Loading activity…",
  "activity.showing": "{{count}} entries",
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

function me(permissions: string[]) {
  return {
    id: "u-admin",
    email: "superadmin@demo.school",
    display_name: "Super Admin",
    locale: "en",
    roles: ["super_admin"],
    permissions,
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [
      { key: "dashboard", label_key: "nav.dashboard", path: "/", module: "core" },
      { key: "activity", label_key: "nav.activity", path: "/activity", module: "core" },
    ],
    modules: [],
    locale: "en",
    languages: ["en", "am"],
  };
}

function entry(overrides: Record<string, unknown> = {}) {
  return {
    seq: 7,
    ts: "2026-01-02T03:04:05.000000Z",
    actor_type: "user",
    actor_id: "u-manager",
    actor_name: "Marta Manager",
    on_behalf_of: null,
    on_behalf_of_name: null,
    via: "web",
    module: "sample",
    entity_type: "sample_note",
    entity_id: "note-1",
    action: "sample.notes.create",
    before: null,
    after: { content: "Hello", author_name: "Marta Manager" },
    reason: "Parent requested a note",
    reverts_id: null,
    ...overrides,
  };
}

const OPTIONS = {
  modules: ["sample"],
  actions: ["sample.notes.create", "sample.notes.update"],
  actors: [
    { id: "u-manager", actor_type: "user", name: "Marta Manager" },
    { id: "c-1", actor_type: "controller", name: null },
  ],
};

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("activity page", () => {
  it("shows entries with actor, module and before/after changes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/me")) return json(me(["audit.activity.view"]));
        if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
        if (url.endsWith("/api/v1/audit/activity/options")) return json(OPTIONS);
        if (url.includes("/api/v1/audit/activity")) {
          return json({
            items: [
              entry(),
              entry({
                seq: 8,
                actor_type: "controller",
                actor_id: "c-1",
                actor_name: null,
                module: null,
                entity_type: null,
                entity_id: null,
                action: "auth.controller_session",
                after: null,
                reason: null,
              }),
            ],
            next_cursor: null,
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    renderAt("/activity");

    const first = await screen.findByTestId("activity-entry-7");
    expect(first).toHaveTextContent("sample.notes.create");
    expect(first).toHaveTextContent("Sample module");
    expect(first).toHaveTextContent("Marta Manager");
    expect(first).toHaveTextContent("Parent requested a note");
    expect(screen.getByTestId("activity-count")).toHaveTextContent("2 entries");

    fireEvent.click(screen.getByText("Changes"));
    expect(screen.getByTestId("activity-changes-7")).toHaveTextContent("content");
    expect(screen.getByTestId("activity-changes-7")).toHaveTextContent("Hello");

    const controller = screen.getByTestId("activity-entry-8");
    expect(controller).toHaveTextContent("Controller");
    expect(controller).not.toHaveTextContent("Marta Manager");
  });

  it("sends the selected filters to the API", async () => {
    const requested: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/me")) return json(me(["audit.activity.view"]));
        if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
        if (url.endsWith("/api/v1/audit/activity/options")) return json(OPTIONS);
        if (url.includes("/api/v1/audit/activity")) {
          requested.push(url);
          return json({ items: [], next_cursor: null });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    renderAt("/activity");
    await screen.findByTestId("activity-empty");
    await screen.findByTestId("activity-filter-actor");

    fireEvent.change(screen.getByTestId("activity-filter-actor"), {
      target: { value: "u-manager" },
    });
    fireEvent.change(screen.getByTestId("activity-filter-module"), {
      target: { value: "sample" },
    });
    fireEvent.change(screen.getByTestId("activity-filter-action"), {
      target: { value: "sample.notes.update" },
    });
    fireEvent.change(screen.getByTestId("activity-filter-entity-type"), {
      target: { value: "sample_note" },
    });
    fireEvent.change(screen.getByTestId("activity-filter-entity-id"), {
      target: { value: "note-1" },
    });
    fireEvent.change(screen.getByTestId("activity-filter-from"), {
      target: { value: "2026-01-02" },
    });
    fireEvent.change(screen.getByTestId("activity-filter-to"), {
      target: { value: "2026-01-05" },
    });
    fireEvent.click(screen.getByTestId("activity-apply"));

    await waitFor(() => expect(requested.length).toBeGreaterThan(0));
    const params = new URL(requested[requested.length - 1], "http://localhost").searchParams;
    expect(params.get("actor_id")).toBe("u-manager");
    expect(params.get("module")).toBe("sample");
    expect(params.get("action")).toBe("sample.notes.update");
    expect(params.get("entity_type")).toBe("sample_note");
    expect(params.get("entity_id")).toBe("note-1");
    expect(params.get("date_from")).toBe("2026-01-02T00:00:00.000Z");
    expect(params.get("date_to")).toBe("2026-01-05T23:59:59.999Z");

    fireEvent.click(screen.getByTestId("activity-clear"));
    await waitFor(() => {
      const cleared = new URL(requested[requested.length - 1], "http://localhost");
      expect(cleared.search).toBe("");
    });
  });

  it("explains a permission denial without calling the activity API", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/me")) return json(me([]));
      if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/activity");

    expect(await screen.findByTestId("activity-permission")).toHaveTextContent(
      "You do not have permission to view the activity history.",
    );
    const paths = fetchMock.mock.calls.map(([input]) => String(input));
    expect(paths.some((path) => path.includes("/api/v1/audit/activity"))).toBe(false);
  });
});
