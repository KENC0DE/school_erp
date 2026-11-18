import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionDetail } from "./types";
import {
  COUNTS,
  DETAIL,
  LEVEL,
  SECTION,
  SESSION,
  YEAR,
  json,
  navigation,
  renderAt,
  session,
} from "./testing";

interface MockRequest {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}

let requests: MockRequest[] = [];
let permissions: string[] = [];
let detail: SessionDetail = DETAIL;

function updatedDetail(status: SessionDetail["status"]): SessionDetail {
  return { ...detail, status, row_version: detail.row_version + 1 };
}

function stubRoutes(overrides?: (request: MockRequest) => Response | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const request: MockRequest = {
        url,
        method: (init?.method ?? "GET").toUpperCase(),
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      };
      requests.push(request);
      if (url.endsWith("/api/v1/auth/me")) return json(session(permissions));
      if (url.endsWith("/api/v1/auth/me/navigation")) return json(navigation());
      if (url.endsWith("/api/v1/themes/active")) return json({}, 404);
      if (url.endsWith("/api/v1/themes/available")) return json({ items: [] });
      const override = overrides?.(request);
      if (override) return override;
      if (url.includes("/api/v1/academics/academic-years")) {
        return json({ items: [YEAR], total: 1, current_year_id: YEAR.id });
      }
      if (url.includes("/api/v1/academics/levels")) {
        return json({ items: [LEVEL], total: 1, scope: {} });
      }
      if (url.includes("/api/v1/academics/sections")) {
        return json({ items: [SECTION], total: 1 });
      }
      if (request.method === "GET" && /\/api\/v1\/attendance(\?.*)?$/.test(url)) {
        return json({ items: [SESSION], next_cursor: null, total: 1 });
      }
      if (request.method === "GET" && url.includes("/api/v1/attendance/session-1")) {
        return json(detail);
      }
      if (request.method === "POST" && url.endsWith("/api/v1/attendance")) {
        return json(
          {
            ...detail,
            id: "session-2",
            date: "2026-10-02",
            counts: { ...COUNTS, total: 0, present: 0, absent: 0 },
            records: [],
            roster: [],
          },
          201,
        );
      }
      if (request.method === "POST" && url.endsWith("/records")) {
        const body = request.body as { items?: { student_id: string; status: string }[] };
        const records = detail.records.map((entry) => {
          const change = body.items?.find((item) => item.student_id === entry.student_id);
          return change ? { ...entry, status: change.status as typeof entry.status } : entry;
        });
        detail = { ...detail, records, row_version: detail.row_version + 1 };
        return json(detail);
      }
      if (request.method === "POST" && url.endsWith("/submit")) {
        detail = updatedDetail("submitted");
        return json(detail);
      }
      if (request.method === "POST" && url.endsWith("/lock")) {
        detail = updatedDetail("locked");
        return json(detail);
      }
      if (request.method === "POST" && url.endsWith("/reopen")) {
        detail = updatedDetail("open");
        return json(detail);
      }
      throw new Error(`Unexpected request: ${request.method} ${url}`);
    }),
  );
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
  requests = [];
  permissions = ["attendance.view", "attendance.record", "attendance.manage"];
  detail = DETAIL;
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("attendance registers", () => {
  it("lists registers and saves a corrected entry through the roster grid", async () => {
    stubRoutes();
    renderAt("/attendance");

    await screen.findByTestId("attendance-table");
    expect(screen.getByText("Grade 5 · Grade 5 A")).toBeInTheDocument();
    expect(screen.getByText("2 present · 1 absent")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "2026-10-01" }));
    await screen.findByTestId("attendance-roster");
    expect(screen.getByText("Abebe Bekele Tesfaye")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("attendance-status-student-1"), {
      target: { value: "absent" },
    });
    fireEvent.change(screen.getByTestId("attendance-reason-student-1"), {
      target: { value: "Family matter" },
    });
    await waitFor(() =>
      expect(screen.getByTestId("attendance-save")).toBeEnabled(),
    );
    fireEvent.click(screen.getByTestId("attendance-save"));

    await waitFor(() => {
      const saved = requests.find(
        (request) =>
          request.method === "POST" &&
          request.url.endsWith("/api/v1/attendance/session-1/records"),
      );
      expect(saved?.body).toEqual({
        items: [
          {
            student_id: "student-1",
            status: "absent",
            reason: "Family matter",
            late_minutes: null,
          },
        ],
      });
    });
    await screen.findByText("Attendance saved.");
  });

  it("opens a register for the selected section and date", async () => {
    stubRoutes();
    renderAt("/attendance");

    await screen.findByTestId("attendance-table");
    fireEvent.click(screen.getByTestId("attendance-open"));
    await screen.findByTestId("attendance-create-section");
    await waitFor(() =>
      expect(screen.getByTestId("attendance-create-section")).toHaveValue(SECTION.id),
    );
    fireEvent.change(screen.getByTestId("attendance-create-date"), {
      target: { value: "2026-10-02" },
    });
    fireEvent.click(screen.getByTestId("attendance-create-save"));

    await waitFor(() => {
      const posted = requests.find(
        (request) =>
          request.method === "POST" &&
          request.url.endsWith("/api/v1/attendance"),
      );
      expect(posted?.body).toEqual({
        year_id: YEAR.id,
        section_id: SECTION.id,
        date: "2026-10-02",
        notes: null,
      });
    });
    await screen.findByText("The register is ready.");
  });

  it("submits and locks a register when the user may manage it", async () => {
    stubRoutes();
    renderAt("/attendance");

    await screen.findByTestId("attendance-table");
    fireEvent.click(screen.getByRole("button", { name: "2026-10-01" }));
    await screen.findByTestId("attendance-roster");

    fireEvent.click(screen.getByTestId("attendance-submit"));
    await screen.findByText("Submitted");
    fireEvent.click(screen.getByTestId("attendance-lock"));
    await screen.findByText("Locked");
    expect(screen.getByTestId("attendance-reopen")).toBeInTheDocument();
  });

  it("shows the permission state when attendance.view is missing", async () => {
    permissions = [];
    stubRoutes();
    renderAt("/attendance");

    await screen.findByText("See attendance registers");
  });
});
