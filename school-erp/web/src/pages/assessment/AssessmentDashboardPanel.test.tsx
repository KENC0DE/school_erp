import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  dashboard,
  dashboardAnomaly,
  dashboardRow,
  dashboardRoutes,
  stubAssessment,
  renderAssessment,
  type DashboardRouteOptions,
  type MockRequest,
} from "./testing";

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function openDashboard() {
  renderAssessment();
  fireEvent.click(await screen.findByTestId("assessment-tab-dashboard"));
  return screen.findByTestId("dashboard-completion");
}

function stub(options: DashboardRouteOptions = {}, permissions?: string[]) {
  stubAssessment(
    permissions ?? ["assessment.view", "assessment.manage"],
    (request: MockRequest) => dashboardRoutes(request, options),
  );
}

describe("web marks progress dashboard", () => {
  it("shows completion per section and teacher, the overdue row and anomalies", async () => {
    stub({
      data: dashboard({
        rows: [
          dashboardRow({
            overdue: true,
            completion_percent: "70",
            status: "draft",
          }),
        ],
        anomalies: [
          dashboardAnomaly(),
          dashboardAnomaly({
            kind: "average_outlier",
            assessment_id: "exam-2",
            title: "Quiz 4",
            count: 2,
            value: null,
            average_percent: "10",
            norm_percent: "53.33",
          }),
        ],
        summary: {
          sections: 1,
          assessments: 3,
          expected: 30,
          entered: 21,
          completion_percent: "70",
          overdue: 1,
          anomalies: 2,
        },
      }),
    });

    await openDashboard();

    expect(screen.getByTestId("dashboard-year")).toHaveValue("year-1");
    expect(screen.getByTestId("dashboard-term")).toHaveValue("term-1");
    expect(screen.getAllByText("Grade 5 G5A").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Mathematics").length).toBeGreaterThan(0);
    expect(screen.getByText("Hanna Girma")).toBeInTheDocument();
    expect(screen.getByText("21/30")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-completion")).toHaveTextContent("70%");
    expect(screen.getByTestId("dashboard-overdue")).toHaveTextContent("1");
    expect(screen.getByTestId("dashboard-anomalies")).toHaveTextContent("2");
    expect(screen.getAllByText("Overdue").length).toBeGreaterThan(0);
    expect(screen.getByText("21 of 30 marks entered")).toBeInTheDocument();

    expect(screen.getByTestId("dashboard-anomaly-identical")).toHaveTextContent(
      "Every mark is 5",
    );
    expect(screen.getByTestId("dashboard-anomaly-identical")).toHaveTextContent(
      "10 identical marks in one assessment.",
    );
    expect(
      screen.getByTestId("dashboard-anomaly-average_outlier"),
    ).toHaveTextContent("Average 10% is far from the norm");
    expect(
      screen.getByTestId("dashboard-anomaly-average_outlier"),
    ).toHaveTextContent("The section and subject norm is 53.33%.");
  });

  it("sends reminders for the chosen term and reports how many went out", async () => {
    const reminded: MockRequest[] = [];
    stub({ reminded });

    await openDashboard();
    fireEvent.click(screen.getByTestId("dashboard-remind"));

    await waitFor(() => expect(reminded).toHaveLength(1));
    expect(reminded[0].url).toContain("/api/v1/assessment/dashboard/remind");
    expect(reminded[0].body).toEqual({
      year_id: "year-1",
      term_id: "term-1",
      section_id: null,
      subject_id: null,
    });
    await waitFor(() =>
      expect(screen.getByTestId("dashboard-notice")).toHaveTextContent(
        "1 reminders sent.",
      ),
    );
  });

  it("hides the reminder action without assessment.manage", async () => {
    stub({}, ["assessment.view"]);

    await openDashboard();

    expect(screen.queryByTestId("dashboard-remind")).toBeNull();
    expect(screen.getByText("Hanna Girma")).toBeInTheDocument();
  });

  it("shows the empty state when no assessment exists in the term", async () => {
    stub({
      data: dashboard({
        rows: [],
        anomalies: [],
        summary: {
          sections: 0,
          assessments: 0,
          expected: 0,
          entered: 0,
          completion_percent: "0",
          overdue: 0,
          anomalies: 0,
        },
      }),
    });

    await openDashboard();

    expect(screen.getByText("No marks to review")).toBeInTheDocument();
    expect(
      screen.getByText("Progress appears once assessments exist."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-anomaly-empty")).toBeInTheDocument();
  });
});
