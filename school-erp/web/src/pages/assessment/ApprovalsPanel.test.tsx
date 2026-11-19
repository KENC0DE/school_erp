import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  approvalRoutes,
  markSubmission,
  renderAssessment,
  stubAssessment,
  type ApprovalRouteOptions,
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

function submitted() {
  return markSubmission({
    id: "submission-1",
    status: "submitted",
    submitted_at: "2026-11-10T08:00:00Z",
    scores: 3,
    entered: 2,
  });
}

function stub(options: ApprovalRouteOptions, permissions?: string[]) {
  stubAssessment(
    permissions ?? [
      "assessment.view",
      "assessment.approve",
      "assessment.publish",
    ],
    (request: MockRequest) => approvalRoutes(request, options),
  );
}

async function openApprovals() {
  renderAssessment();
  fireEvent.click(await screen.findByTestId("assessment-tab-approvals"));
  return screen.findByText("Mathematics");
}

describe("web marks approvals", () => {
  it("reviews submitted marks and approves them with an optional comment", async () => {
    const actions: MockRequest[] = [];
    stub({ submissions: [submitted()], actions });

    await openApprovals();
    expect(screen.getByTestId("approval-year")).toHaveValue("year-1");
    expect(screen.getByTestId("approval-term")).toHaveValue("term-1");
    expect(screen.getByTestId("approval-status")).toHaveValue("submitted");
    expect(screen.getByText("2 of 3 marks")).toBeInTheDocument();
    expect(screen.getAllByText("Submitted").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByTestId("approval-review-G5A-sub-1"));

    await waitFor(() =>
      expect(screen.getByTestId("approval-sheets")).toHaveTextContent("Quiz 1"),
    );
    expect(screen.getByTestId("approval-sheets")).toHaveTextContent(
      "0 of 3 marks",
    );

    fireEvent.click(screen.getByTestId("approval-approve"));

    await waitFor(() => expect(actions).toHaveLength(1));
    expect(actions[0].url).toContain(
      "/api/v1/assessment/submissions/submission-1/approve",
    );
    expect(actions[0].body).toEqual({ row_version: 1, note: null });
    await waitFor(() =>
      expect(screen.getByTestId("approval-notice")).toHaveTextContent(
        "Marks approved.",
      ),
    );
  });

  it("requires a comment before rejecting and sends it with the decision", async () => {
    const actions: MockRequest[] = [];
    stub({ submissions: [submitted()], actions });

    await openApprovals();
    fireEvent.click(screen.getByTestId("approval-review-G5A-sub-1"));

    const reject = await screen.findByTestId("approval-reject");
    expect(reject).toBeDisabled();
    expect(screen.getByTestId("approval-comment-required")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("approval-comment"), {
      target: { value: "Two students are still missing." },
    });
    expect(screen.getByTestId("approval-reject")).toBeEnabled();
    fireEvent.click(screen.getByTestId("approval-reject"));

    await waitFor(() => expect(actions).toHaveLength(1));
    expect(actions[0].url).toContain(
      "/api/v1/assessment/submissions/submission-1/reject",
    );
    expect(actions[0].body).toEqual({
      row_version: 1,
      note: "Two students are still missing.",
    });
    await waitFor(() =>
      expect(screen.getByTestId("approval-notice")).toHaveTextContent(
        "Marks returned to the teacher.",
      ),
    );
  });

  it("publishes approved marks and hides publish without the permission", async () => {
    const actions: MockRequest[] = [];
    stub(
      {
        submissions: [
          markSubmission({
            id: "submission-2",
            status: "approved",
            approved_at: "2026-11-11T08:00:00Z",
          }),
        ],
        actions,
      },
      ["assessment.view", "assessment.publish"],
    );

    await openApprovals();
    await waitFor(() =>
      expect(screen.getByTestId("approval-status")).toBeTruthy(),
    );
    fireEvent.change(screen.getByTestId("approval-status"), {
      target: { value: "approved" },
    });
    fireEvent.click(await screen.findByTestId("approval-review-G5A-sub-1"));

    const publish = await screen.findByTestId("approval-publish");
    expect(screen.queryByTestId("approval-approve")).toBeNull();
    expect(screen.queryByTestId("approval-reject")).toBeNull();
    fireEvent.click(publish);

    await waitFor(() => expect(actions).toHaveLength(1));
    expect(actions[0].url).toContain(
      "/api/v1/assessment/submissions/submission-2/publish",
    );
    expect(actions[0].body).toEqual({ row_version: 1, note: null });
    await waitFor(() =>
      expect(screen.getByTestId("approval-notice")).toHaveTextContent(
        "Marks published.",
      ),
    );
  });

  it("shows no decision buttons without the approve permission", async () => {
    stub({ submissions: [submitted()] }, ["assessment.view"]);

    await openApprovals();
    fireEvent.click(screen.getByTestId("approval-review-G5A-sub-1"));

    await screen.findByTestId("approval-sheets");
    expect(screen.queryByTestId("approval-approve")).toBeNull();
    expect(screen.queryByTestId("approval-reject")).toBeNull();
    expect(screen.queryByTestId("approval-publish")).toBeNull();
    expect(screen.getByTestId("approval-readonly")).toHaveTextContent(
      "Submitted",
    );
  });
});
