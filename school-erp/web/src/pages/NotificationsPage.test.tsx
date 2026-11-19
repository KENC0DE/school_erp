import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "../App";

const messages: Record<string, string> = {
  "app.name": "School ERP",
  "app.short_name": "SE",
  "nav.dashboard": "Dashboard",
  "nav.notifications": "Notifications",
  "settings.enum.en": "English",
  "settings.enum.am": "Amharic",
  "common.loading": "Loading…",
  "common.error": "Something went wrong",
  "common.language": "Language",
  "common.theme": "Theme",
  "common.theme.light": "Light",
  "common.theme.dark": "Dark",
  "auth.logout": "Sign out",
  "notifications.title": "Notifications",
  "notifications.intro": "Messages for you.",
  "notifications.empty": "You have no notifications.",
  "notifications.empty_unread": "You have no unread notifications.",
  "notifications.unread": "{{count}} unread",
  "notifications.all": "All",
  "notifications.unread_only": "Unread",
  "notifications.mark_read": "Mark as read",
  "notifications.mark_all_read": "Mark all as read",
  "notifications.read": "Read",
  "notifications.open_item": "Open",
  "notifications.loading": "Loading notifications…",
  "notifications.category.general": "General",
  "notifications.category.academic": "Academic",
};

interface Row {
  id: string;
  template_key: string;
  category: string;
  title: string;
  body: string;
  params: Record<string, unknown>;
  link: string | null;
  channels: string[];
  read: boolean;
  read_at: string | null;
  created_at: string | null;
}

let rows: Row[] = [];
let requests: { method: string; url: string }[] = [];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function row(overrides: Partial<Row> = {}): Row {
  return {
    id: "n-1",
    template_key: "account.welcome",
    category: "general",
    title: "Welcome to Alpha Academy",
    body: "Hello Hanna, your account is ready.",
    params: { name: "Hanna" },
    link: "/dashboard",
    channels: ["in_app"],
    read: false,
    read_at: null,
    created_at: "2026-01-02T03:04:05.000000Z",
    ...overrides,
  };
}

function unreadCount() {
  return rows.filter((item) => !item.read).length;
}

function me() {
  return {
    id: "u-1",
    email: "hanna@demo.school",
    display_name: "Hanna",
    locale: "en",
    roles: ["limited"],
    permissions: [],
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [
      { key: "dashboard", label_key: "nav.dashboard", path: "/", module: "core" },
      {
        key: "notifications",
        label_key: "nav.notifications",
        path: "/notifications",
        module: "core",
      },
    ],
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
  localStorage.setItem("erp.access_token", "test-access-token");
  rows = [row(), row({ id: "n-2", category: "academic", title: "Results published", link: null })];
  requests = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/v1/auth/me")) return json(me());
      if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
      if (url.endsWith("/api/v1/themes/active")) return json({}, 404);
      if (url.endsWith("/api/v1/themes/available")) return json({ items: [] });
      if (url.endsWith("/api/v1/notifications/unread-count")) {
        return json({ unread: unreadCount() });
      }
      if (url.endsWith("/api/v1/notifications/read-all") && method === "POST") {
        requests.push({ method, url });
        const updated = unreadCount();
        rows = rows.map((item) => ({
          ...item,
          read: true,
          read_at: item.read_at ?? "2026-01-03T00:00:00.000000Z",
        }));
        return json({ updated });
      }
      if (url.match(/\/api\/v1\/notifications\/[^/]+\/read$/) && method === "POST") {
        requests.push({ method, url });
        const id = url.split("/").at(-2);
        rows = rows.map((item) =>
          item.id === id
            ? { ...item, read: true, read_at: "2026-01-03T00:00:00.000000Z" }
            : item,
        );
        return json(rows.find((item) => item.id === id));
      }
      if (url.includes("/api/v1/notifications")) {
        requests.push({ method, url });
        const unreadOnly = url.includes("unread_only=true");
        return json({
          items: unreadOnly ? rows.filter((item) => !item.read) : rows,
          unread: unreadCount(),
          next_offset: null,
        });
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    }),
  );
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("notifications page", () => {
  it("shows the inbox with an unread count and marks one message read", async () => {
    renderAt("/notifications");

    const first = await screen.findByTestId("notification-n-1");
    expect(first).toHaveTextContent("Welcome to Alpha Academy");
    expect(first).toHaveTextContent("Hello Hanna, your account is ready.");
    expect(screen.getByTestId("notifications-unread")).toHaveTextContent("2 unread");
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", "/dashboard");

    fireEvent.click(screen.getAllByRole("button", { name: "Mark as read" })[0]);

    await waitFor(() =>
      expect(
        requests.some(
          (request) =>
            request.method === "POST" &&
            request.url.endsWith("/api/v1/notifications/n-1/read"),
        ),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(screen.getByTestId("notifications-unread")).toHaveTextContent("1 unread"),
    );
    expect(screen.getByTestId("notification-n-1")).toHaveTextContent("Read");
  });

  it("filters to unread messages and explains an empty result", async () => {
    rows = [row({ read: true, read_at: "2026-01-03T00:00:00.000000Z" })];
    renderAt("/notifications");

    expect(await screen.findByTestId("notification-n-1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Unread" }));

    expect(await screen.findByText("You have no unread notifications.")).toBeInTheDocument();
    expect(screen.queryByTestId("notification-n-1")).not.toBeInTheDocument();
    expect(
      requests.some(
        (request) => request.method === "GET" && request.url.includes("unread_only=true"),
      ),
    ).toBe(true);
  });

  it("marks every message as read", async () => {
    renderAt("/notifications");
    await screen.findByTestId("notification-n-1");

    fireEvent.click(screen.getByRole("button", { name: "Mark all as read" }));

    await waitFor(() =>
      expect(
        requests.some(
          (request) =>
            request.method === "POST" &&
            request.url.endsWith("/api/v1/notifications/read-all"),
        ),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(screen.getByTestId("notifications-unread")).toHaveTextContent("0 unread"),
    );
    expect(screen.queryByRole("button", { name: "Mark as read" })).not.toBeInTheDocument();
  });
});
