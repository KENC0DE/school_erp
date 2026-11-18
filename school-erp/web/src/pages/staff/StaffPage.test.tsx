import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEPARTMENT,
  POSITION,
  STAFF,
  STAFF_DETAIL,
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
      if (request.method === "GET" && /\/api\/v1\/staff(\?.*)?$/.test(url)) {
        return json({ items: [STAFF], next_cursor: null, total: 1 });
      }
      if (request.method === "GET" && url.includes("/api/v1/staff/departments")) {
        return json({ items: [DEPARTMENT], total: 1 });
      }
      if (request.method === "GET" && url.includes("/api/v1/staff/positions")) {
        return json({ items: [POSITION], total: 1 });
      }
      if (request.method === "GET" && url.includes("/api/v1/staff/leave-types")) {
        return json({ items: [], total: 0 });
      }
      if (request.method === "GET" && url.includes("/api/v1/staff/leave-calendar")) {
        return json({ from_date: "2026-11-01", to_date: "2026-11-30", items: [], total: 0 });
      }
      if (request.method === "POST" && url.endsWith("/api/v1/staff")) {
        return json(STAFF_DETAIL, 201);
      }
      if (request.method === "POST" && url.endsWith("/api/v1/staff/departments")) {
        return json({ ...DEPARTMENT, id: "dept-2", code: "arts", name: "Arts" }, 201);
      }
      throw new Error(`Unexpected request: ${request.method} ${url}`);
    }),
  );
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
  requests = [];
  permissions = [
    "staff.view",
    "staff.manage",
    "staff.leave.view",
    "staff.leave.manage",
  ];
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("staff directory", () => {
  it("lists staff and applies search and status filters", async () => {
    stubRoutes();
    renderAt("/staff");

    await screen.findByText("Abebe Bekele Tesfaye");
    expect(screen.getByTestId("staff-table")).toBeInTheDocument();
    expect(screen.getByText("1 staff")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("staff-search"), {
      target: { value: "Abebe" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(
        requests.some(
          (request) =>
            request.method === "GET" &&
            request.url.includes("/api/v1/staff?") &&
            request.url.includes("q=Abebe"),
        ),
      ).toBe(true);
    });

    fireEvent.change(screen.getByTestId("staff-status-filter"), {
      target: { value: "active" },
    });

    await waitFor(() => {
      expect(
        requests.some(
          (request) =>
            request.method === "GET" &&
            request.url.includes("q=Abebe") &&
            request.url.includes("status=active"),
        ),
      ).toBe(true);
    });
  });

  it("adds a staff member with both name scripts", async () => {
    stubRoutes();
    renderAt("/staff");

    await screen.findByText("Abebe Bekele Tesfaye");
    fireEvent.click(screen.getByTestId("staff-create-open"));

    fireEvent.change(screen.getByTestId("name-given_name_en"), {
      target: { value: "Hanna" },
    });
    fireEvent.change(screen.getByTestId("name-father_name_en"), {
      target: { value: "Alemu" },
    });
    fireEvent.change(screen.getByTestId("name-grandfather_name_en"), {
      target: { value: "Desta" },
    });
    fireEvent.change(screen.getByTestId("name-given_name_am"), {
      target: { value: "ሃና" },
    });
    fireEvent.change(screen.getByTestId("staff-number-input"), {
      target: { value: "STF-2026-0099" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const posted = requests.find(
        (request) =>
          request.method === "POST" && request.url.endsWith("/api/v1/staff"),
      );
      expect(posted).toBeTruthy();
      expect(posted?.body).toMatchObject({
        person: {
          given_name_en: "Hanna",
          father_name_en: "Alemu",
          grandfather_name_en: "Desta",
          given_name_am: "ሃና",
        },
        staff_number: "STF-2026-0099",
        status: "active",
      });
    });

    expect(await screen.findByTestId("staff-created")).toHaveTextContent(
      "Abebe Bekele Tesfaye was added.",
    );
  });

  it("manages departments from the catalog tab", async () => {
    stubRoutes();
    renderAt("/staff");

    await screen.findByText("Abebe Bekele Tesfaye");
    fireEvent.click(screen.getByRole("tab", { name: "Departments" }));
    expect(await screen.findByTestId("departments-table")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add department" }));
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "arts" },
    });
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Arts" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const posted = requests.find(
        (request) =>
          request.method === "POST" &&
          request.url.endsWith("/api/v1/staff/departments"),
      );
      expect(posted?.body).toMatchObject({ code: "arts", name: "Arts" });
    });
  });

  it("hides the module when the user cannot see staff", async () => {
    permissions = ["students.view"];
    stubRoutes();
    renderAt("/staff");

    expect(
      await screen.findByText("See staff records"),
    ).toBeInTheDocument();
  });
});
