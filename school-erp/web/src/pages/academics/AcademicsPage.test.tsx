import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LEVELS,
  PROFILES,
  SCOPE,
  SUBJECTS,
  YEARS,
  json,
  renderAcademics,
  stubAcademics,
  term,
  year,
  type MockRequest,
} from "./testing";

function checklistRoutes(request: MockRequest): Response {
  const { url } = request;
  if (url.includes("/api/v1/academics/scope")) return json(SCOPE);
  if (url.includes("/api/v1/academics/levels")) return json(LEVELS);
  if (url.includes("/api/v1/academics/curriculum-profiles")) return json({ items: [], total: 0 });
  if (url.includes("/api/v1/academics/academic-years")) {
    const draft = year({ status: "draft", current_term_id: null, terms: [term({ status: "pending" })] });
    return json({ items: [draft], total: 1, current_year_id: null });
  }
  if (url.includes("/api/v1/academics/subjects")) return json({ items: [], total: 0 });
  if (url.includes("/api/v1/academics/sections")) return json({ items: [], total: 0 });
  throw new Error(`Unexpected request: ${request.method} ${url}`);
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("academics page", () => {
  it("shows the setup checklist and opens the step screen", async () => {
    stubAcademics(["academics.view", "academics.manage"], checklistRoutes);
    renderAcademics();

    await waitFor(() =>
      expect(screen.getByTestId("setup-progress")).toHaveTextContent("1 of 5 steps complete"),
    );
    expect(screen.getByTestId("setup-step-scope")).toHaveAttribute("data-done", "true");
    expect(screen.getByTestId("setup-step-years")).toHaveAttribute("data-done", "false");
    expect(screen.getByTestId("setup-step-subjects")).toHaveAttribute("data-done", "false");

    const yearStep = screen.getByTestId("setup-step-years");
    fireEvent.click(within(yearStep).getByRole("button", { name: "Open" }));

    expect(await screen.findByTestId("year-code")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Years & terms" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("denies access without the view permission", async () => {
    stubAcademics([], () => {
      throw new Error("Academics should not request data without permission");
    });
    renderAcademics();

    expect(await screen.findByTestId("academics-permission")).toHaveTextContent(
      "You do not have permission to view academic structure.",
    );
  });

  it("saves the school scope with an audit reason", async () => {
    let putBody: Record<string, unknown> | null = null;
    stubAcademics(["academics.view", "academics.manage"], (request) => {
      if (request.method === "PUT" && request.url.endsWith("/api/v1/academics/scope")) {
        putBody = request.body;
        return json({ ...SCOPE, first_level: 1 });
      }
      return checklistRoutes(request);
    });
    renderAcademics();

    fireEvent.click(await screen.findByTestId("academics-tab-scope"));
    const first = await screen.findByLabelText("First grade level");
    await waitFor(() => expect((first as HTMLSelectElement).options.length).toBeGreaterThan(1));
    fireEvent.change(first, { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Reason (optional)"), {
      target: { value: "School now starts at Grade 1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save scope" }));

    await waitFor(() => expect(putBody).not.toBeNull());
    expect(putBody).toEqual({
      first_level: 1,
      last_level: 12,
      reason: "School now starts at Grade 1",
    });
    expect(await screen.findByText("Academic scope updated")).toBeInTheDocument();
  });

  it("creates a draft academic year", async () => {
    let postBody: Record<string, unknown> | null = null;
    stubAcademics(["academics.view", "academics.manage"], (request) => {
      if (request.method === "POST" && request.url.endsWith("/api/v1/academics/academic-years")) {
        postBody = request.body;
        return json(year({ id: "year-2", code: "2027", name: "2027/28", status: "draft" }), 201);
      }
      if (request.url.includes("/curriculum-profiles")) return json(PROFILES);
      return checklistRoutes(request);
    });
    renderAcademics();

    fireEvent.click(await screen.findByTestId("academics-tab-years"));
    fireEvent.change(await screen.findByTestId("year-code"), { target: { value: "2027" } });
    fireEvent.change(screen.getByTestId("year-name"), { target: { value: "2027/28" } });
    fireEvent.change(screen.getByTestId("year-start"), { target: { value: "2027-09-01" } });
    fireEvent.change(screen.getByTestId("year-end"), { target: { value: "2028-06-30" } });
    fireEvent.click(screen.getByRole("button", { name: "Create year" }));

    await waitFor(() => expect(postBody).not.toBeNull());
    expect(postBody).toEqual({
      code: "2027",
      name: "2027/28",
      name_am: null,
      start_date: "2027-09-01",
      end_date: "2028-06-30",
      curriculum_profile_id: null,
    });
  });

  it("opens and closes a year and its terms", async () => {
    const posted: string[] = [];
    stubAcademics(["academics.view", "academics.manage"], (request) => {
      if (request.method === "POST") {
        posted.push(request.url);
        return json(year());
      }
      if (request.url.includes("/api/v1/academics/academic-years")) return json(YEARS);
      return checklistRoutes(request);
    });
    renderAcademics();

    fireEvent.click(await screen.findByTestId("academics-tab-years"));
    const schedule = await screen.findByTestId("year-row-2026");
    expect(schedule).toHaveTextContent("Open");

    fireEvent.click(within(screen.getByTestId("term-row-2026-1")).getByRole("button", { name: "Close term" }));
    await waitFor(() =>
      expect(posted).toContain("http://localhost:8000/api/v1/academics/academic-years/year-1/terms/term-1/close"),
    );
    fireEvent.click(within(screen.getByTestId("year-row-2026")).getByRole("button", { name: "Close year" }));
    await waitFor(() =>
      expect(posted).toContain("http://localhost:8000/api/v1/academics/academic-years/year-1/close"),
    );
  });

  it("lists subjects in the setup step", async () => {
    stubAcademics(["academics.view", "academics.manage"], (request) => {
      if (request.url.includes("/subjects")) return json(SUBJECTS);
      return checklistRoutes(request);
    });
    renderAcademics();

    fireEvent.click(await screen.findByTestId("academics-tab-subjects"));
    await screen.findByTestId("subject-code");
    expect(screen.getAllByText("Mathematics").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Art").length).toBeGreaterThan(0);
  });
});
