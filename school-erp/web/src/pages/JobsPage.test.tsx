import { QueryClient } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders, AppRoutes } from "../App";

const messages: Record<string, string> = {
  "app.name": "School ERP",
  "app.short_name": "SE",
  "nav.dashboard": "Dashboard",
  "nav.jobs": "Background jobs",
  "settings.enum.en": "English",
  "settings.enum.am": "Amharic",
  "common.loading": "Loading…",
  "common.error": "Something went wrong",
  "common.language": "Language",
  "common.theme": "Theme",
  "common.theme.light": "Light",
  "common.theme.dark": "Dark",
  "auth.logout": "Sign out",
  "jobs.title": "Background jobs",
  "jobs.intro": "Long-running work such as thumbnails and notification delivery.",
  "jobs.loading": "Loading background jobs…",
  "jobs.empty": "No background jobs match this filter.",
  "jobs.status_filter": "Status",
  "jobs.kind_filter": "Kind",
  "jobs.all_statuses": "All statuses",
  "jobs.all_kinds": "All kinds",
  "jobs.col_kind": "Kind",
  "jobs.col_status": "Status",
  "jobs.col_progress": "Progress",
  "jobs.col_created": "Created",
  "jobs.col_actions": "Actions",
  "jobs.progress": "{{percent}}% complete",
  "jobs.retry": "Retry",
  "jobs.retrying": "Retrying…",
  "jobs.retried": "The job was queued again.",
  "jobs.retry_unavailable": "This failure cannot be retried from here.",
  "jobs.status.queued": "Queued",
  "jobs.status.running": "Running",
  "jobs.status.succeeded": "Succeeded",
  "jobs.status.failed": "Failed",
  "jobs.status.cancelled": "Cancelled",
  "jobs.kind.ping": "Health check",
  "jobs.kind.files_thumbnail": "Image thumbnail",
  "jobs.kind.notifications_delivery": "Notification delivery",
  "jobs.kind.other": "Other",
  "jobs.error.generic": "The job failed. Try again, and contact support if it keeps failing.",
  "jobs.error.thumbnail": "The thumbnail could not be generated.",
  "jobs.error.notification": "One or more messages could not be delivered.",
};

interface Job {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  error_key: string | null;
  retryable: boolean;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

let jobs: Job[] = [];
let requests: { method: string; url: string }[] = [];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    kind: "files.thumbnail",
    status: "failed",
    progress: 40,
    error_key: "jobs.error.thumbnail",
    retryable: true,
    created_at: "2026-01-02T03:04:05.000000Z",
    started_at: "2026-01-02T03:04:06.000000Z",
    finished_at: "2026-01-02T03:04:07.000000Z",
    ...overrides,
  };
}

function me() {
  return {
    id: "u-1",
    email: "hanna@demo.school",
    display_name: "Hanna",
    locale: "en",
    roles: ["super_admin"],
    permissions: ["*"],
    is_controller: false,
  };
}

function navigation() {
  return {
    items: [
      { key: "dashboard", label_key: "nav.dashboard", path: "/", module: "core" },
      { key: "jobs", label_key: "nav.jobs", path: "/jobs", module: "core" },
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
  jobs = [
    job(),
    job({
      id: "job-2",
      kind: "notifications.delivery",
      status: "failed",
      progress: 100,
      error_key: "jobs.error.notification",
      retryable: false,
    }),
    job({
      id: "job-3",
      kind: "ping",
      status: "succeeded",
      progress: 100,
      error_key: null,
      retryable: false,
    }),
  ];
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
      if (url.match(/\/api\/v1\/jobs\/[^/]+\/retry$/) && method === "POST") {
        requests.push({ method, url });
        const id = url.split("/").at(-2);
        jobs = jobs.map((item) =>
          item.id === id
            ? {
                ...item,
                status: "queued" as const,
                progress: 0,
                error_key: null,
                retryable: false,
                started_at: null,
                finished_at: null,
              }
            : item,
        );
        return json(jobs.find((item) => item.id === id));
      }
      if (url.includes("/api/v1/jobs")) {
        requests.push({ method, url });
        const parsed = new URL(url, "http://localhost");
        const status = parsed.searchParams.get("status");
        const kind = parsed.searchParams.get("kind");
        return json({
          items: jobs.filter(
            (item) => (!status || item.status === status) && (!kind || item.kind === kind),
          ),
          next_cursor: null,
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

describe("jobs page", () => {
  it("shows progress, translated labels and user-safe errors", async () => {
    renderAt("/jobs");

    const first = await screen.findByTestId("job-job-1");
    expect(first).toHaveTextContent("Image thumbnail");
    expect(first).toHaveTextContent("Failed");
    expect(first).toHaveTextContent("40% complete");
    expect(first).toHaveTextContent("The thumbnail could not be generated.");
    expect(first).not.toHaveTextContent("Traceback");
    expect(within(first).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");

    const second = screen.getByTestId("job-job-2");
    expect(second).toHaveTextContent("Notification delivery");
    expect(second).toHaveTextContent("One or more messages could not be delivered.");
    expect(second).toHaveTextContent("This failure cannot be retried from here.");
    expect(within(second).queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();

    expect(screen.getByTestId("job-job-3")).toHaveTextContent("Health check");
    expect(screen.getByTestId("job-job-3")).toHaveTextContent("Succeeded");
  });

  it("filters the list through the API", async () => {
    renderAt("/jobs");

    await screen.findByTestId("job-job-1");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "failed" } });

    await waitFor(() =>
      expect(requests.some((request) => request.url.includes("status=failed"))).toBe(true),
    );
    expect(await screen.findByTestId("job-job-2")).toBeInTheDocument();
    expect(screen.queryByTestId("job-job-3")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "ping" } });
    await waitFor(() =>
      expect(requests.some((request) => request.url.includes("kind=ping"))).toBe(true),
    );
    expect(await screen.findByText("No background jobs match this filter.")).toBeInTheDocument();
  });

  it("retries a failed job and refreshes its row", async () => {
    renderAt("/jobs");

    const first = await screen.findByTestId("job-job-1");
    fireEvent.click(within(first).getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(
        requests.some(
          (request) =>
            request.method === "POST" && request.url.endsWith("/api/v1/jobs/job-1/retry"),
        ),
      ).toBe(true),
    );

    expect(await screen.findByRole("status")).toHaveTextContent("The job was queued again.");
    await waitFor(() => expect(screen.getByTestId("job-job-1")).toHaveTextContent("Queued"));
    const refreshed = screen.getByTestId("job-job-1");
    expect(refreshed).toHaveTextContent("0% complete");
    expect(within(refreshed).queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("shows an empty state without jobs", async () => {
    jobs = [];
    renderAt("/jobs");

    expect(await screen.findByText("No background jobs match this filter.")).toBeInTheDocument();
  });
});
