import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "../App";

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
    <AppProviders queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
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

function navigation(items: Array<{ key: string; path: string }>) {
  return {
    items: items.map((item) => ({ ...item, label_key: `nav.${item.key}`, module: "core" })),
    modules: [],
    locale: "en",
    languages: ["en", "am"],
  };
}

const limitedRole = {
  id: "role-limited",
  key: "limited",
  name: "Limited User",
  description: null,
  is_system: false,
  is_active: true,
  require_totp: false,
  permissions: [{ permission: "sample.notes.view", scope: "all" }],
};

const teacherRole = {
  id: "role-teacher",
  key: "teacher",
  name: "Teacher",
  description: null,
  is_system: true,
  is_active: true,
  require_totp: false,
  permissions: [{ permission: "ai.use", scope: "all" }],
};

const policyPermission = {
  code: "sample.notes.view",
  module: "sample",
  scopes: ["all"],
  label_key: "sample.perm.view",
};

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("roles page", () => {
  it("renders the permission matrix and saves a removed permission", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/auth/me")) {
        return json(me(["roles.view", "roles.manage", "users.view", "users.manage", "*"]));
      }
      if (url.endsWith("/api/v1/auth/me/navigation")) {
        return json(navigation([{ key: "dashboard", path: "/" }]));
      }
      if (url.endsWith("/api/v1/rbac/roles") && method === "GET") {
        return json({ items: [limitedRole], next_cursor: null });
      }
      if (url.endsWith("/api/v1/rbac/permissions")) {
        return json({ items: [policyPermission], next_cursor: null, can_grant: ["*"] });
      }
      if (url.endsWith("/rbac/roles/role-limited") && method === "PATCH") {
        return json(limitedRole);
      }
      if (url.endsWith("/rbac/roles/role-limited/permissions") && method === "PUT") {
        return json({ ...limitedRole, permissions: [] });
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/roles");

    const checkbox = await screen.findByTestId("permission-sample.notes.view-all");
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByTestId("roles-save"));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/rbac/roles/role-limited/permissions") && init?.method === "PUT",
      );
      expect(call).toBeTruthy();
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({ permissions: [] });
    });
  });
});

describe("users page", () => {
  const user = {
    id: "user-limited",
    email: "limited@demo.school",
    phone: null,
    display_name: "Limited User",
    is_active: true,
    locale: "en",
    must_change_password: false,
    last_login_at: null,
    locked_until: null,
    roles: ["limited"],
  };

  function baseMock(extra?: (url: string, method: string) => Response | undefined) {
    return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const handled = extra?.(url, method);
      if (handled) return handled;
      if (url.endsWith("/api/v1/auth/me")) {
        return json(me(["users.view", "users.manage", "roles.view", "roles.manage"]));
      }
      if (url.endsWith("/api/v1/auth/me/navigation")) {
        return json(navigation([{ key: "dashboard", path: "/" }, { key: "users", path: "/users" }]));
      }
      if (url.endsWith("/api/v1/auth/users") && method === "GET") {
        return json({ items: [user], next_cursor: null });
      }
      if (url.endsWith("/api/v1/rbac/roles") && method === "GET") {
        return json({ items: [limitedRole, teacherRole], next_cursor: null });
      }
      if (url.endsWith("/api/v1/rbac/users/user-limited/permissions")) {
        return json({
          user_id: "user-limited",
          roles: ["limited"],
          effective: { permissions: ["sample.notes.view"], scopes: { "sample.notes.view": ["all"] } },
        });
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    });
  }

  it("assigns and removes roles from an existing user", async () => {
    const fetchMock = baseMock((url, method) => {
      if (url.endsWith("/rbac/users/user-limited/roles") && method === "POST") {
        return json({ ok: true });
      }
      if (url.endsWith("/rbac/users/user-limited/roles/role-limited") && method === "DELETE") {
        return json({ ok: true });
      }
      if (url.endsWith("/api/v1/auth/users/user-limited") && method === "PATCH") {
        return json(user);
      }
      return undefined;
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/users");

    fireEvent.click(await screen.findByTestId("user-row-limited@demo.school"));
    const teacherBox = await screen.findByTestId("user-role-teacher");
    fireEvent.click(teacherBox);
    fireEvent.click(screen.getByTestId("user-role-limited"));
    fireEvent.click(screen.getByTestId("users-save-roles"));

    await waitFor(() => {
      const assigned = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/rbac/users/user-limited/roles") && init?.method === "POST",
      );
      const removed = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/rbac/users/user-limited/roles/role-limited") &&
          init?.method === "DELETE",
      );
      expect(JSON.parse(String(assigned?.[1]?.body))).toEqual({ role_id: "role-teacher" });
      expect(removed).toBeTruthy();
    });
  });

  it("invites a user with a starting role", async () => {
    const fetchMock = baseMock((url, method) => {
      if (url.endsWith("/api/v1/auth/users") && method === "POST") {
        return json({
          ...user,
          id: "user-invited",
          email: "new.teacher@demo.school",
          roles: ["teacher"],
          invitation_sent: true,
          invitation_link: "http://localhost:8000/reset-password?token=abc",
        });
      }
      return undefined;
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/users");

    fireEvent.click(await screen.findByTestId("invite-open"));
    fireEvent.change(screen.getByTestId("invite-name"), { target: { value: "New Teacher" } });
    fireEvent.change(screen.getByTestId("invite-email"), {
      target: { value: "new.teacher@demo.school" },
    });
    fireEvent.click(screen.getByTestId("invite-role-teacher"));
    fireEvent.click(screen.getByTestId("invite-submit"));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/api/v1/auth/users") && init?.method === "POST",
      );
      expect(call).toBeTruthy();
      expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
        email: "new.teacher@demo.school",
        display_name: "New Teacher",
        role_ids: ["role-teacher"],
      });
    });
  });
});
