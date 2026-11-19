import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  gradeRoutes,
  gradeScale,
  json,
  renderAssessment,
  scaleAssignment,
  stubAssessment,
  type MockRequest,
} from "./testing";

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

async function openGrades() {
  renderAssessment();
  fireEvent.click(await screen.findByTestId("assessment-tab-grades"));
  return screen.findByTestId("grade-panel");
}

describe("grade rules editor", () => {
  it("auto-adjusts band edges, validates live and posts the derived bands", async () => {
    const posts: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.manage"], (request) => {
      if (request.method === "POST" && request.url.endsWith("/api/v1/assessment/scales")) {
        posts.push(request);
        return json(gradeScale({ name: "Lower primary scale" }), 201);
      }
      return gradeRoutes(request);
    });
    await openGrades();

    fireEvent.click(await screen.findByTestId("grade-new"));
    fireEvent.change(screen.getByTestId("grade-name"), {
      target: { value: "Lower primary scale" },
    });

    expect(screen.getByTestId("grade-invalid")).toBeInTheDocument();
    expect(screen.getByTestId("grade-band-to-0")).toHaveValue("100");

    fireEvent.change(screen.getByTestId("grade-band-label-0"), { target: { value: "All" } });
    await waitFor(() => expect(screen.queryByTestId("grade-invalid")).toBeNull());

    fireEvent.click(screen.getByTestId("grade-add-band"));
    expect(screen.getByTestId("grade-band-to-0")).toHaveValue("50");
    expect(screen.getByTestId("grade-band-to-1")).toHaveValue("100");
    expect(screen.getByTestId("grade-invalid")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("grade-band-from-1"), { target: { value: "60" } });
    expect(screen.getByTestId("grade-band-to-0")).toHaveValue("60");
    fireEvent.change(screen.getByTestId("grade-band-label-1"), { target: { value: "Merit" } });
    await waitFor(() => expect(screen.queryByTestId("grade-invalid")).toBeNull());

    fireEvent.change(screen.getByTestId("grade-band-from-1"), { target: { value: "0" } });
    expect(screen.getByTestId("grade-invalid")).toBeInTheDocument();
    expect(screen.getByTestId("grade-save")).toBeDisabled();
    fireEvent.change(screen.getByTestId("grade-band-from-1"), { target: { value: "60" } });

    fireEvent.click(screen.getByTestId("grade-save"));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body).toMatchObject({
      name: "Lower primary scale",
      type: "numeric_bands",
      is_default: false,
      lower_bound: "0",
      upper_bound: "100",
      precision: 2,
      rounding: "half_up",
      bands: [
        {
          min_value: "0",
          max_value: "60",
          label: "All",
          is_pass: true,
          sort_order: 0,
        },
        {
          min_value: "60",
          max_value: "100",
          label: "Merit",
          is_pass: true,
          sort_order: 1,
        },
      ],
    });
    expect(await screen.findByTestId("grade-saved")).toHaveTextContent(
      "The grade scale was saved.",
    );
  });

  it("keeps the loaded bands when only the name changes", async () => {
    const patches: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.manage"], (request) => {
      if (
        request.method === "PATCH" &&
        request.url.endsWith("/api/v1/assessment/scales/scale-1")
      ) {
        patches.push(request);
        return json(gradeScale({ name: "Renamed scale" }));
      }
      return gradeRoutes(request);
    });
    await openGrades();

    fireEvent.click(await screen.findByTestId("grade-edit-scale-1"));
    fireEvent.change(screen.getByTestId("grade-name"), { target: { value: "Renamed scale" } });
    fireEvent.click(screen.getByTestId("grade-save"));

    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0].body).toMatchObject({
      row_version: 1,
      name: "Renamed scale",
      lower_bound: "0",
      upper_bound: "100",
    });
    expect(patches[0].body).not.toHaveProperty("bands");
  });

  it("tests a mark, assigns a scale by context and removes assignments and scales", async () => {
    const requests: MockRequest[] = [];
    const assignments = [scaleAssignment()];
    stubAssessment(["assessment.view", "assessment.manage"], (request) => {
      if (request.method === "POST" && request.url.endsWith("/api/v1/assessment/scale-assignments")) {
        requests.push(request);
        return json(scaleAssignment({ id: "assignment-2", context: "level" }), 201);
      }
      if (request.url.includes("/api/v1/assessment/scale-assignments")) {
        requests.push(request);
        return json({ items: assignments, total: assignments.length });
      }
      if (request.method === "POST" && request.url.endsWith("/api/v1/assessment/scales/scale-1/test")) {
        requests.push(request);
        return json({
          value: "75",
          label: "C+",
          remark: null,
          gpa_points: "3",
          is_pass: true,
          color: null,
          band_min: "75",
          band_max: "85",
          scale_name: "School grading scale",
          scale_version: 1,
        });
      }
      if (request.method === "DELETE") {
        requests.push(request);
        return json({ id: "removed", deleted: true });
      }
      return gradeRoutes(request, [gradeScale(), gradeScale({ id: "scale-2", name: "Alt", is_default: false })], assignments);
    });
    await openGrades();

    expect(await screen.findByTestId("grade-list")).toBeInTheDocument();
    expect(screen.getByTestId("grade-default-scale-1")).toHaveTextContent("Default");
    expect(screen.getByTestId("grade-bands-scale-1")).toHaveTextContent("75–<85 C+");

    fireEvent.change(screen.getByTestId("grade-test-scale"), { target: { value: "scale-1" } });
    fireEvent.change(screen.getByTestId("grade-test-value"), { target: { value: "75" } });
    fireEvent.click(screen.getByTestId("grade-test-run"));
    expect(await screen.findByTestId("grade-test-result")).toHaveTextContent("“75” is C+.");

    fireEvent.change(screen.getByTestId("assignment-scale"), { target: { value: "scale-2" } });
    fireEvent.change(screen.getByTestId("assignment-context"), { target: { value: "level" } });
    fireEvent.change(screen.getByTestId("assignment-level"), { target: { value: "lvl-1" } });
    fireEvent.click(screen.getByTestId("assignment-add"));

    await waitFor(() => {
      expect(
        requests.some(
          (request) =>
            request.method === "POST" &&
            request.url.endsWith("/api/v1/assessment/scale-assignments"),
        ),
      ).toBe(true);
    });
    const assignmentPost = requests.find(
      (request) =>
        request.method === "POST" &&
        request.url.endsWith("/api/v1/assessment/scale-assignments"),
    );
    expect(assignmentPost?.body).toEqual({
      scale_id: "scale-2",
      context: "level",
      assessment_id: null,
      subject_id: null,
      level_id: "lvl-1",
      stage_id: null,
    });

    expect(await screen.findByTestId("assignment-row-assignment-1")).toHaveTextContent(
      "Grade 5",
    );
    fireEvent.click(screen.getByTestId("assignment-remove-assignment-1"));
    await waitFor(() =>
      expect(
        requests.some(
          (request) =>
            request.method === "DELETE" &&
            request.url.endsWith("/api/v1/assessment/scale-assignments/assignment-1"),
        ),
      ).toBe(true),
    );

    fireEvent.click(screen.getByTestId("grade-delete-scale-1"));
    await waitFor(() =>
      expect(
        requests.some(
          (request) =>
            request.method === "DELETE" && request.url.endsWith("/api/v1/assessment/scales/scale-1"),
        ),
      ).toBe(true),
    );
    expect(await screen.findByTestId("grade-deleted")).toHaveTextContent(
      "The grade scale was removed.",
    );
  });

  it("lets a read-only viewer test a mark but never edit the rules", async () => {
    stubAssessment(["assessment.view"], (request) => {
      if (request.url.includes("/api/v1/assessment/scale-assignments")) {
        return json({ items: [scaleAssignment()], total: 1 });
      }
      return gradeRoutes(request);
    });
    await openGrades();

    expect(await screen.findByTestId("grade-list")).toBeInTheDocument();
    expect(screen.queryByTestId("grade-new")).toBeNull();
    expect(screen.queryByTestId("grade-edit-scale-1")).toBeNull();
    expect(screen.queryByTestId("grade-delete-scale-1")).toBeNull();
    expect(screen.queryByTestId("assignment-add")).toBeNull();
    expect(screen.queryByTestId("assignment-remove-assignment-1")).toBeNull();
    expect(screen.getByTestId("grade-test-run")).toBeInTheDocument();
  });
});
