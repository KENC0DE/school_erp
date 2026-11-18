import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MockRequest } from "./testing";
import {
  CONTRACT,
  LEAVE_BALANCE,
  LEAVE_REQUEST,
  LEAVE_TYPE,
  STAFF_DETAIL,
  YEAR,
  json,
  navigation,
  renderAt,
  session,
} from "./testing";

let requests: MockRequest[] = [];
let permissions: string[] = [];
let requestRows = [LEAVE_REQUEST];

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

      if (request.method === "GET" && url.endsWith("/api/v1/staff/staff-1")) {
        return json(STAFF_DETAIL);
      }
      if (url.endsWith("/api/v1/staff/staff-1/contracts")) {
        return json({ items: [CONTRACT], total: 1 });
      }
      if (url.endsWith("/api/v1/staff/staff-1/qualifications")) {
        return json({ items: [], total: 0 });
      }
      if (url.endsWith("/api/v1/staff/staff-1/teaching-assignments")) {
        return json({ items: [], total: 0 });
      }
      if (url.includes("/api/v1/staff/staff-1/documents")) {
        return json({ items: [] });
      }
      if (url.includes("/api/v1/staff/leave-balances")) {
        return json({ items: [LEAVE_BALANCE], total: 1 });
      }
      if (url.includes("/api/v1/staff/leave-requests")) {
        if (request.method === "POST") {
          return json(requestRows[0], 201);
        }
        return json({ items: requestRows, total: requestRows.length });
      }
      if (url.includes("/api/v1/staff/leave-types")) {
        return json({ items: [LEAVE_TYPE], total: 1 });
      }
      if (url.includes("/api/v1/academics/academic-years")) {
        return json({ items: [YEAR], total: 1, current_year_id: YEAR.id });
      }
      if (url.includes("/api/v1/academics/subjects")) {
        return json({ items: [], total: 0 });
      }
      if (url.includes("/api/v1/academics/sections")) {
        return json({ items: [], total: 0 });
      }
      if (request.method === "POST" && url.endsWith("/api/v1/staff/leave-requests")) {
        return json({ ...LEAVE_REQUEST, id: "request-new" }, 201);
      }
      if (request.method === "POST" && url.endsWith("/submit")) {
        return json({ ...LEAVE_REQUEST, status: "submitted" });
      }
      if (request.method === "POST" && url.endsWith("/approve")) {
        return json({ ...LEAVE_REQUEST, status: "approved" });
      }
      throw new Error(`Unexpected request: ${request.method} ${url}`);
    }),
  );
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
  requests = [];
  requestRows = [LEAVE_REQUEST];
  permissions = [
    "staff.view",
    "staff.manage",
    "staff.contracts.view",
    "staff.contracts.manage",
    "staff.leave.view",
    "staff.leave.request",
    "staff.leave.approve",
    "staff.leave.manage",
  ];
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("staff profile", () => {
  it("shows the overview and contract information when permitted", async () => {
    stubRoutes();
    renderAt("/staff/staff-1");

    expect(await screen.findByText("Abebe Bekele Tesfaye")).toBeInTheDocument();
    expect(screen.getByTestId("staff-overview")).toHaveTextContent(
      "Head of science.",
    );
    expect(screen.getByText("STF-2026-0001")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Contracts" }));
    expect(await screen.findByTestId("contracts-table")).toBeInTheDocument();
    expect(screen.getByText("Permanent")).toBeInTheDocument();
    expect(screen.getByText("ETB 15,000.00")).toBeInTheDocument();
  });

  it("does not show contracts without the contract permission", async () => {
    permissions = ["staff.view", "staff.leave.view", "staff.leave.request"];
    stubRoutes();
    renderAt("/staff/staff-1");

    await screen.findByText("Abebe Bekele Tesfaye");
    expect(screen.queryByRole("tab", { name: "Contracts" })).not.toBeInTheDocument();
  });

  it("creates, submits and approves a leave request", async () => {
    stubRoutes();
    renderAt("/staff/staff-1");

    await screen.findByText("Abebe Bekele Tesfaye");
    fireEvent.click(screen.getByRole("tab", { name: "Leave requests" }));

    expect(await screen.findByTestId("leave-balances-table")).toBeInTheDocument();
    expect(screen.getByText("17")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Request leave" }));
    fireEvent.change(screen.getByTestId("leave-request-type"), {
      target: { value: LEAVE_TYPE.id },
    });
    fireEvent.change(screen.getByTestId("leave-request-year"), {
      target: { value: YEAR.id },
    });
    fireEvent.change(screen.getByTestId("leave-request-start-input"), {
      target: { value: "2026-11-02" },
    });
    fireEvent.change(screen.getByTestId("leave-request-end-input"), {
      target: { value: "2026-11-03" },
    });
    fireEvent.change(screen.getByTestId("leave-request-reason"), {
      target: { value: "Family event" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const posted = requests.find(
        (request) =>
          request.method === "POST" &&
          request.url.endsWith("/api/v1/staff/leave-requests"),
      );
      expect(posted?.body).toMatchObject({
        staff_id: "staff-1",
        year_id: YEAR.id,
        leave_type_id: LEAVE_TYPE.id,
        start_date: "2026-11-02",
        end_date: "2026-11-03",
        reason: "Family event",
      });
    });

    fireEvent.click(await screen.findByRole("button", { name: "Submit for approval" }));
    await waitFor(() => {
      expect(
        requests.some(
          (request) =>
            request.method === "POST" &&
            request.url.endsWith("/api/v1/staff/leave-requests/request-1/submit"),
        ),
      ).toBe(true);
    });
  });

  it("approves a submitted request with a decision note", async () => {
    requestRows = [{ ...LEAVE_REQUEST, status: "submitted" as const }];
    stubRoutes();
    renderAt("/staff/staff-1");

    await screen.findByText("Abebe Bekele Tesfaye");
    fireEvent.click(screen.getByRole("tab", { name: "Leave requests" }));
    await screen.findByTestId("leave-requests-table");

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.change(screen.getByTestId("leave-decision-note"), {
      target: { value: "Approved by HR" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const posted = requests.find(
        (request) =>
          request.method === "POST" &&
          request.url.endsWith("/api/v1/staff/leave-requests/request-1/approve"),
      );
      expect(posted?.body).toEqual({ note: "Approved by HR" });
    });
  });
});
