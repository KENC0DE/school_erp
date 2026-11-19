import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  TERM,
  YEAR,
  portalChild,
  portalResult,
  portalResults,
  portalRoutes,
  renderAssessment,
  stubAssessment,
  type MockRequest,
  type PortalRouteOptions,
} from "./testing";

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function stub(options: PortalRouteOptions, roles: string[] = ["parent"]) {
  stubAssessment(
    ["assessment.view"],
    (request: MockRequest) => portalRoutes(request, options),
    roles,
  );
}

describe("web portal results", () => {
  it("shows a parent both children with their published subject results", async () => {
    stub({
      data: portalResults({
        children: [
          portalChild(),
          portalChild({
            student_id: "stu-2",
            student_number: "STU-2026-0002",
            student_name: "Sara Tesfaye",
            results: [
              portalResult({
                snapshot_id: "snap-2",
                term_name: "Semester 1",
                result: {
                  ...portalResult().result,
                  student_id: "stu-2",
                  student_number: "STU-2026-0002",
                  student_name: "Sara Tesfaye",
                  percent: "52",
                  total: "26",
                  out_of: "50",
                  grade_label: "C",
                },
              }),
            ],
          }),
        ],
      }),
    });

    renderAssessment();

    await screen.findByTestId("portal-results");
    await screen.findByText("Abel Bekele");
    // The staff tabs never appear for a portal account.
    expect(screen.queryByTestId("assessment-tab-marks")).toBeNull();
    expect(screen.getAllByTestId("portal-child")).toHaveLength(2);
    expect(screen.getByText("Abel Bekele")).toBeInTheDocument();
    expect(screen.getByText("Sara Tesfaye")).toBeInTheDocument();
    expect(screen.getByText("STU-2026-0002")).toBeInTheDocument();
    // Published term label and section come from the snapshot.
    expect(screen.getAllByText("Semester 1 result")).toHaveLength(2);
    expect(
      screen.getAllByText("Grade 5 G5A · Published 2026-11-15"),
    ).toHaveLength(2);
    expect(screen.getAllByText("Mathematics")).toHaveLength(2);
    expect(screen.getAllByText("71.38%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("35.69/50").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Overall").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Pass").length).toBeGreaterThan(0);
  });

  it("switches the academic year and refetches the published view", async () => {
    const urls: string[] = [];
    const nextYear = {
      ...YEAR,
      id: "year-2",
      code: "2027",
      name: "2027/28",
      current_term_id: "term-2",
      terms: [{ ...TERM, id: "term-2", year_id: "year-2" }],
    };
    stub({
      data: portalResults(),
      years: { items: [YEAR, nextYear], total: 2, current_year_id: "year-1" },
    });
    const original = globalThis.fetch;
    // Record the portal URL the panel requests after a year change.
    vi.stubGlobal(
      "fetch",
      async (input: RequestInfo | URL, init?: RequestInit) => {
        urls.push(String(input));
        return original(input, init);
      },
    );

    renderAssessment();
    await screen.findByTestId("portal-results");
    expect(screen.getByTestId("portal-year")).toHaveValue("year-1");

    fireEvent.change(screen.getByTestId("portal-year"), {
      target: { value: "year-2" },
    });

    await waitFor(() =>
      expect(
        urls.some((url) =>
          url.includes("/assessment/portal/results?year_id=year-2"),
        ),
      ).toBe(true),
    );
  });

  it("shows a student only themselves", async () => {
    stub(
      {
        data: portalResults({
          children: [
            portalChild({
              results: [
                portalResult({
                  kind: "year",
                  term_id: null,
                  term_name: null,
                }),
              ],
            }),
          ],
        }),
      },
      ["student"],
    );

    renderAssessment();

    await screen.findByTestId("portal-results");
    await screen.findByText("Abel Bekele");
    expect(screen.getAllByTestId("portal-child")).toHaveLength(1);
    expect(screen.getByText("Abel Bekele")).toBeInTheDocument();
    expect(screen.getByText("Year result")).toBeInTheDocument();
  });

  it("explains that results appear after publication", async () => {
    stub({ data: portalResults({ children: [] }) });

    renderAssessment();

    expect(
      await screen.findByText("No published results yet"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "When the school publishes marks, they appear here for you.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("portal-empty")).toBeInTheDocument();
  });
});
