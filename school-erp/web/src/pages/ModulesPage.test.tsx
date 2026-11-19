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
  "common.loading": "Loading…",
  "common.yes": "Yes",
  "common.no": "No",
  "common.enabled": "Enabled",
  "common.disabled": "Disabled",
  "common.error": "Something went wrong",
  "modules.title": "Modules",
  "modules.intro": "A module is available only when it is licensed, enabled and permitted.",
  "modules.gates_hint": "Three gates decide availability.",
  "modules.read_only": "You can view module state, but changing it needs the modules.manage permission.",
  "modules.back": "Back to settings",
  "modules.version": "Version {{version}}",
  "modules.core": "Core",
  "modules.not_licensable": "Always available",
  "modules.licensed": "Licensed",
  "modules.enabled": "Enabled",
  "modules.permitted": "Permitted",
  "modules.available": "Available",
  "modules.depends_on": "Depends on",
  "modules.dependants": "Used by",
  "modules.no_dependencies": "Nothing",
  "modules.dependency_unavailable": "{{dependency}} (not available)",
  "modules.core_always_on": "Core modules are always on and cannot be turned off.",
  "modules.unlicensed_hint": "This module is not in the current licence, so it cannot be turned on.",
  "modules.not_permitted_hint": "Your roles do not include this module's permissions.",
  "modules.dependency_blocked": "Turn on {{dependencies}} first.",
  "modules.dependants_blocked": "Turn off {{dependants}} first.",
  "modules.dependency_disabled": "That module cannot be turned on until its dependency is available.",
  "modules.dependants_enabled": "Another enabled module depends on this one. Turn it off first.",
  "modules.audit_hint": "Every change is recorded in the audit history immediately.",
};

function json(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
    headers: { get: () => null },
  } as unknown as Response;
}

function jsonError(status: number, body: unknown): Response {
  return {
    ok: false,
    status,
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
      { key: "settings", label_key: "nav.settings", path: "/settings", module: "core" },
      { key: "modules", label_key: "nav.modules", path: "/settings/modules", module: "core" },
    ],
    modules: [],
    locale: "en",
    languages: ["en", "am"],
  };
}

function moduleItem(overrides: Record<string, unknown> = {}) {
  return {
    key: "sample",
    name: "Sample module",
    version: "0.1.0",
    description: "A sample module.",
    core: false,
    licensable: true,
    depends_on: [],
    dependencies: [],
    dependants: [],
    blocked_by: [],
    permitted: true,
    licensed: true,
    enabled: true,
    available: true,
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("modules page", () => {
  it("shows the three gates and dependency warnings", async () => {
    const core = moduleItem({
      key: "core",
      name: "Core",
      core: true,
      licensable: false,
    });
    const base = moduleItem({
      key: "base_module",
      name: "Base module",
      enabled: true,
      dependants: [{ key: "child_module", name: "Child module", enabled: true }],
    });
    const child = moduleItem({
      key: "child_module",
      name: "Child module",
      enabled: false,
      available: false,
      depends_on: ["base_module"],
      dependencies: [{ key: "base_module", name: "Base module", available: false }],
      blocked_by: ["base_module"],
      dependants: [],
    });
    const unlicensed = moduleItem({
      key: "reports",
      name: "Reports",
      licensed: false,
      enabled: false,
      available: false,
    });
    const hidden = moduleItem({
      key: "library",
      name: "Library",
      permitted: false,
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/me")) {
          return json(me(["modules.view", "modules.manage"]));
        }
        if (url.endsWith("/api/v1/auth/me/navigation")) {
          return json(navigation());
        }
        if (url.endsWith("/api/v1/system/modules")) {
          return json({
            items: [moduleItem(), core, base, child, unlicensed, hidden],
            next_cursor: null,
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    renderAt("/settings/modules");

    expect(await screen.findByTestId("module-licensed-sample")).toHaveTextContent("Yes");
    expect(screen.getByTestId("module-enabled-sample")).toHaveTextContent("Yes");
    expect(screen.getByTestId("module-permitted-sample")).toHaveTextContent("Yes");
    expect(screen.getByTestId("module-available-sample")).toHaveTextContent("Yes");

    expect(screen.getByTestId("module-licensed-reports")).toHaveTextContent("No");
    expect(screen.getByTestId("module-permitted-library")).toHaveTextContent("No");
    expect(screen.getByTestId("module-blocked-child_module")).toHaveTextContent(
      "Turn on Base module first.",
    );
    expect(screen.getByTestId("module-dependants-base_module")).toHaveTextContent(
      "Turn off Child module first.",
    );

    expect(screen.getByTestId("module-toggle-core")).toBeDisabled();
    expect(screen.getByTestId("module-toggle-child_module")).toBeDisabled();
    expect(screen.getByTestId("module-toggle-base_module")).toBeDisabled();
    expect(screen.getByTestId("module-toggle-reports")).toBeDisabled();
  });

  it("toggles a module and audits the new state through the API", async () => {
    let enabled = true;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/auth/me")) {
        return json(me(["modules.view", "modules.manage"]));
      }
      if (url.endsWith("/api/v1/auth/me/navigation")) {
        return json(navigation());
      }
      if (url.endsWith("/api/v1/system/modules") && method === "GET") {
        return json({
          items: [moduleItem({ enabled, available: enabled })],
          next_cursor: null,
        });
      }
      if (url.endsWith("/api/v1/system/modules/sample") && method === "PUT") {
        enabled = Boolean(JSON.parse(String(init?.body)).enabled);
        return json(moduleItem({ enabled, available: enabled }));
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/settings/modules");

    const toggle = await screen.findByTestId("module-toggle-sample");
    expect(toggle).toBeChecked();
    fireEvent.click(toggle);

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/api/v1/system/modules/sample") && init?.method === "PUT",
      );
      expect(call).toBeTruthy();
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({ enabled: false });
    });
    await waitFor(() =>
      expect(screen.getByTestId("module-enabled-sample")).toHaveTextContent("No"),
    );
  });

  it("is read-only without modules.manage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/me")) {
          return json(me(["modules.view"]));
        }
        if (url.endsWith("/api/v1/auth/me/navigation")) {
          return json(navigation());
        }
        if (url.endsWith("/api/v1/system/modules")) {
          return json({ items: [moduleItem()], next_cursor: null });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    renderAt("/settings/modules");

    expect(await screen.findByTestId("module-toggle-sample")).toBeDisabled();
    expect(
      screen.getByText(
        "You can view module state, but changing it needs the modules.manage permission.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a server dependency conflict in the page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/v1/auth/me")) {
          return json(me(["modules.view", "modules.manage"]));
        }
        if (url.endsWith("/api/v1/auth/me/navigation")) {
          return json(navigation());
        }
        if (url.endsWith("/api/v1/system/modules") && (init?.method ?? "GET") === "GET") {
          return json({
            items: [moduleItem({ enabled: false, available: false })],
            next_cursor: null,
          });
        }
        if (url.endsWith("/api/v1/system/modules/sample") && init?.method === "PUT") {
          return jsonError(409, {
            error: {
              code: "CONFLICT",
              message_key: "modules.dependency_disabled",
              message: "Module 'sample' requires 'base_module' to be enabled first",
              details: { dependency: "base_module" },
              request_id: "req_test",
            },
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    renderAt("/settings/modules");

    fireEvent.click(await screen.findByTestId("module-toggle-sample"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That module cannot be turned on until its dependency is available.",
    );
  });
});
