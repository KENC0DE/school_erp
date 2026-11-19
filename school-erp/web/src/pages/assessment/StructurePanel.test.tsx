import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  baseRoutes,
  json,
  renderAssessment,
  structure,
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

describe("mark structure editor", () => {
  it("creates a structure and warns while the components miss the intended total", async () => {
    const posts: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.manage"], (request) => {
      if (request.method === "POST" && request.url.endsWith("/api/v1/assessment/structures")) {
        posts.push(request);
        return json(structure(), 201);
      }
      return baseRoutes(request);
    });
    renderAssessment();

    expect(await screen.findByTestId("structure-empty")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("structure-new"));
    fireEvent.change(screen.getByTestId("structure-name"), {
      target: { value: "Lower primary" },
    });
    fireEvent.change(screen.getByTestId("component-key-0"), { target: { value: "quiz" } });
    fireEvent.change(screen.getByTestId("component-name-0"), { target: { value: "Quiz" } });
    fireEvent.change(screen.getByTestId("component-max-0"), { target: { value: "10" } });

    expect(await screen.findByTestId("structure-total-warning")).toHaveTextContent(
      "Components add up to 10, not the intended 100.",
    );

    fireEvent.click(screen.getByTestId("component-add"));
    fireEvent.change(screen.getByTestId("component-name-1"), { target: { value: "Exam" } });
    fireEvent.change(screen.getByTestId("component-max-1"), { target: { value: "90" } });

    await waitFor(() => expect(screen.queryByTestId("structure-total-warning")).toBeNull());
    expect(screen.getByTestId("structure-total")).toHaveTextContent("Components total 100");

    fireEvent.click(screen.getByTestId("structure-save"));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body).toEqual({
      year_id: "year-1",
      scope_type: "school",
      level_id: null,
      stage_id: null,
      subject_id: null,
      name: "Lower primary",
      name_am: null,
      year_mode: "average",
      year_weights: null,
      precision: 2,
      rounding: "half_up",
      intended_total: "100",
      descriptive_mode: false,
      components: [
        {
          id: null,
          key: "quiz",
          name: "Quiz",
          name_am: null,
          max_points: "10",
          aggregation: "average",
          absent_counts_as_zero: false,
          best_n: null,
          cap: null,
          sort_order: 0,
          is_active: true,
        },
        {
          id: null,
          key: "component_2",
          name: "Exam",
          name_am: null,
          max_points: "90",
          aggregation: "average",
          absent_counts_as_zero: false,
          best_n: null,
          cap: null,
          sort_order: 1,
          is_active: true,
        },
      ],
    });
    expect(await screen.findByTestId("structure-saved")).toHaveTextContent(
      "The mark structure was saved.",
    );
  });

  it("edits an existing structure with its component ids and aggregation arguments", async () => {
    const patches: MockRequest[] = [];
    stubAssessment(["assessment.view", "assessment.manage"], (request) => {
      if (
        request.method === "PATCH" &&
        request.url.endsWith("/api/v1/assessment/structures/structure-1")
      ) {
        patches.push(request);
        return json({ structure: structure({ name: "Updated" }), recalculation_job_id: null });
      }
      if (request.url.includes("/api/v1/assessment/structures")) {
        return json({ items: [structure()], next_cursor: null, total: 1 });
      }
      return baseRoutes(request);
    });
    renderAssessment();

    fireEvent.click(await screen.findByTestId("structure-edit-structure-1"));
    fireEvent.change(screen.getByTestId("structure-name"), { target: { value: "Updated" } });
    fireEvent.change(screen.getByTestId("component-max-0"), { target: { value: "20" } });
    fireEvent.change(screen.getByTestId("component-max-1"), { target: { value: "80" } });
    fireEvent.change(screen.getByTestId("component-aggregation-0"), {
      target: { value: "best_n" },
    });
    fireEvent.change(screen.getByTestId("component-best-n-0"), { target: { value: "2" } });
    fireEvent.click(screen.getByTestId("structure-save"));

    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0].url).toContain("/api/v1/assessment/structures/structure-1");
    expect(patches[0].body).toMatchObject({
      row_version: 3,
      name: "Updated",
      components: [
        { id: "component-1", key: "quizzes", max_points: "20", aggregation: "best_n", best_n: 2 },
        { id: "component-2", key: "final", max_points: "80", aggregation: "average", best_n: null },
      ],
    });
  });

  it("shows the list but no editor to a read-only viewer", async () => {
    stubAssessment(["assessment.view"], (request) => {
      if (request.url.includes("/api/v1/assessment/structures")) {
        return json({ items: [structure()], next_cursor: null, total: 1 });
      }
      return baseRoutes(request);
    });
    renderAssessment();

    expect(await screen.findByTestId("structure-list")).toBeInTheDocument();
    expect(screen.queryByTestId("structure-new")).toBeNull();
    expect(screen.queryByTestId("structure-edit-structure-1")).toBeNull();
  });
});
