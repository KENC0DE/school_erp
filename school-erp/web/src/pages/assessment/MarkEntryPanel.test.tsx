import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MARK_STUDENTS,
  json,
  markRoutes,
  markSubmission,
  markingWindow,
  renderAssessment,
  scoreItem,
  stubAssessment,
  threeSheets,
  type MarkRouteOptions,
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

async function openMarks() {
  renderAssessment();
  fireEvent.click(await screen.findByTestId("assessment-tab-marks"));
  await screen.findByTestId("mark-entry-panel");
  return screen.findByTestId("mark-cell-0-0");
}

function withSheets(overrides: MarkRouteOptions = {}): MarkRouteOptions {
  return { sheets: threeSheets(), ...overrides };
}

describe("web mark-entry grid", () => {
  it("loads the section sheet and autosaves a typed mark with its row version", async () => {
    const saved: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.enter_marks"], (request) =>
      markRoutes(request, withSheets({ saved })),
    );
    const first = await openMarks();

    expect(screen.getByTestId("mark-year")).toHaveValue("year-1");
    expect(screen.getByTestId("mark-section")).toHaveValue("sec-1");
    expect(screen.getByTestId("mark-subject")).toHaveValue("sub-1");
    expect(screen.getByTestId("mark-term")).toHaveValue("term-1");
    expect(screen.getByText("Abel Bekele")).toBeInTheDocument();
    expect(screen.getByTestId("mark-converted-0-0")).toHaveTextContent("—");

    fireEvent.change(first, { target: { value: "12" } });
    expect(screen.getByTestId("mark-converted-0-0")).toHaveTextContent("8");
    fireEvent.blur(first);

    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0].url).toContain(
      "/api/v1/assessment/assessments/exam-1/scores",
    );
    expect(saved[0].body).toEqual({
      items: [
        {
          student_id: "stu-1",
          raw_score: "12",
          status: "present",
          row_version: null,
        },
      ],
    });
  });

  it("moves down with Enter and records status keys without a value", async () => {
    const saved: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.enter_marks"], (request) =>
      markRoutes(request, withSheets({ saved })),
    );
    const first = await openMarks();

    first.focus();
    expect(document.activeElement).toBe(first);
    fireEvent.change(first, { target: { value: "11" } });
    fireEvent.keyDown(first, { key: "Enter" });

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByTestId("mark-cell-1-0")),
    );
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0].body).toMatchObject({
      items: [{ student_id: "stu-1", raw_score: "11", status: "present" }],
    });

    const second = screen.getByTestId("mark-cell-1-0");
    fireEvent.keyDown(second, { key: "a" });
    await waitFor(() => expect(saved).toHaveLength(2));
    expect(second).toHaveAttribute("data-status", "absent");
    expect(saved[1].body).toMatchObject({
      items: [{ student_id: "stu-2", raw_score: null, status: "absent" }],
    });
    expect(screen.getByTestId("mark-converted-1-0")).toHaveTextContent(
      "Absent",
    );
  });

  it("pastes a column, saving every pasted cell", async () => {
    const saved: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.enter_marks"], (request) =>
      markRoutes(request, withSheets({ saved })),
    );
    const first = await openMarks();

    fireEvent.paste(first, { clipboardData: { getData: () => "12\n13\n14" } });

    await waitFor(() => expect(saved).toHaveLength(3));
    const values = saved
      .map(
        (request) =>
          (request.body?.items as { raw_score: string }[])[0].raw_score,
      )
      .sort();
    expect(values).toEqual(["12", "13", "14"]);
    expect(screen.getByTestId("mark-converted-2-0")).toHaveTextContent("9.33");
  });

  it("shows a conflict banner and reloads the sheet after a stale save", async () => {
    const saved: MockRequest[] = [];
    let rejected = false;
    stubAssessment(["assessment.view", "assessment.enter_marks"], (request) =>
      markRoutes(
        request,
        withSheets({
          saved,
          onSave: () => {
            if (rejected) return null;
            rejected = true;
            return json(
              {
                error: {
                  code: "CONFLICT",
                  message: "The record changed since it was loaded",
                },
              },
              409,
            );
          },
        }),
      ),
    );
    const first = await openMarks();

    fireEvent.change(first, { target: { value: "12" } });
    fireEvent.blur(first);

    expect(await screen.findByTestId("mark-conflict")).toHaveTextContent(
      "This sheet changed elsewhere.",
    );
    fireEvent.click(screen.getByTestId("mark-reload"));
    await waitFor(() =>
      expect(screen.queryByTestId("mark-conflict")).toBeNull(),
    );
    expect(await screen.findByTestId("mark-cell-0-0")).toHaveValue("");
  });

  it("locks the grid when the submission is not a draft and requests a correction", async () => {
    const saved: MockRequest[] = [];
    const sheets = threeSheets();
    sheets["exam-1"].items = MARK_STUDENTS.map((student) =>
      scoreItem(student, {
        score_id: `score-exam-1-${student.studentId}`,
        raw_score: "11",
        row_version: 2,
        converted: "7.33",
      }),
    );
    stubAssessment(
      ["assessment.view", "assessment.enter_marks", "assessment.correct"],
      (request) =>
        markRoutes(
          request,
          withSheets({
            saved,
            sheets,
            submissions: [markSubmission({ status: "locked" })],
          }),
        ),
    );
    const first = await openMarks();

    expect(await screen.findByTestId("mark-readonly")).toHaveTextContent(
      "Marks are locked.",
    );
    expect(first).toBeDisabled();

    fireEvent.click(screen.getByTestId("mark-correction-open"));
    fireEvent.change(await screen.findByTestId("mark-correction-value"), {
      target: { value: "13" },
    });
    fireEvent.change(screen.getByTestId("mark-correction-reason"), {
      target: { value: "Recheck the paper" },
    });
    fireEvent.click(screen.getByTestId("mark-correction-submit"));

    await waitFor(() =>
      expect(
        saved.some((request) =>
          request.url.endsWith("/assessment/corrections"),
        ),
      ).toBe(true),
    );
    const correction = saved.find((request) =>
      request.url.endsWith("/assessment/corrections"),
    );
    expect(correction?.body).toEqual({
      score_id: "score-exam-1-stu-1",
      new_raw: "13",
      new_status: "present",
      reason: "Recheck the paper",
    });
    expect(
      await screen.findByTestId("mark-correction-result"),
    ).toHaveTextContent("The correction request was sent.");
  });

  it("is read-only while the marking window is closed", async () => {
    stubAssessment(["assessment.view", "assessment.enter_marks"], (request) =>
      markRoutes(
        request,
        withSheets({
          windows: [markingWindow({ state: "closed", is_active: false })],
        }),
      ),
    );
    const first = await openMarks();

    expect(await screen.findByTestId("mark-readonly")).toHaveTextContent(
      "The marking window is closed.",
    );
    expect(first).toBeDisabled();
    expect(screen.queryByTestId("mark-correction-open")).toBeNull();
  });

  it("previews an uploaded file and applies only the valid marks", async () => {
    const saved: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.enter_marks"], (request) =>
      markRoutes(request, withSheets({ saved })),
    );
    const first = await openMarks();
    expect(first).toBeInTheDocument();

    const content = [
      "Student number\tStudent\tQuiz 1 (out of 15)",
      "STU-2026-0001\tAbel\t12",
      "STU-9999\tNobody\t8",
      "STU-2026-0002\tSara\t99",
    ].join("\n");
    const file = new File([content], "marks.tsv", {
      type: "text/tab-separated-values",
    });
    fireEvent.change(screen.getByTestId("mark-upload-input"), {
      target: { files: [file] },
    });

    expect(await screen.findByTestId("mark-upload-valid")).toHaveTextContent(
      "1 marks for 1 students are ready to apply.",
    );
    expect(screen.getByTestId("mark-upload-issues")).toHaveTextContent(
      "2 problems found",
    );
    expect(screen.getByText(/Unknown student number/)).toBeInTheDocument();
    expect(screen.getByText(/Above the maximum/)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("mark-upload-apply"));
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0].body).toMatchObject({
      items: [{ student_id: "stu-1", raw_score: "12", status: "present" }],
    });
    expect(await screen.findByTestId("mark-upload-result")).toHaveTextContent(
      "The uploaded marks were saved.",
    );
  });

  it("downloads a filled template as a TSV file", async () => {
    stubAssessment(["assessment.view", "assessment.enter_marks"], (request) =>
      markRoutes(request, withSheets()),
    );
    await openMarks();

    const create = vi.fn((blob: Blob) => `blob:${blob.size}`);
    const revoke = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      value: create,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: revoke,
      configurable: true,
      writable: true,
    });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    fireEvent.click(screen.getByTestId("mark-download"));

    expect(create).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    const blob = create.mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text.split("\n")[0]).toContain("Quiz 1 (out of 15)");
    expect(text).toContain("STU-2026-0001");
  });

  it("opens for the wildcard super admin", async () => {
    stubAssessment(["*"], (request) => markRoutes(request, withSheets()));
    const first = await openMarks();

    expect(first).toBeEnabled();
    expect(screen.queryByTestId("mark-readonly")).toBeNull();
  });

  it("keeps the grid read-only for a viewer without enter permission", async () => {
    stubAssessment(["assessment.view"], (request) =>
      markRoutes(request, withSheets()),
    );
    const first = await openMarks();

    expect(await screen.findByTestId("mark-readonly")).toHaveTextContent(
      "You do not have permission to enter marks.",
    );
    expect(first).toBeDisabled();
  });

  it("reverts an unsaved edit with Escape before it is sent", async () => {
    const saved: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.enter_marks"], (request) =>
      markRoutes(request, withSheets({ saved })),
    );
    const first = await openMarks();

    fireEvent.change(first, { target: { value: "14" } });
    expect(first).toHaveValue("14");
    expect(screen.getByTestId("mark-converted-0-0")).toHaveTextContent("9.33");

    fireEvent.keyDown(first, { key: "Escape" });
    expect(first).toHaveValue("");
    expect(screen.getByTestId("mark-converted-0-0")).toHaveTextContent("—");
    expect(saved).toHaveLength(0);
  });
});
