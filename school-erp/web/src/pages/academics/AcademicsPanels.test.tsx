import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  LEVELS,
  PROFILES,
  SCOPE,
  SUBJECTS,
  YEARS,
  applyResult,
  json,
  renderAcademics,
  section,
  stubAcademics,
  subject,
  type MockRequest,
} from "./testing";

function baseRoutes(request: MockRequest): Response {
  const { url } = request;
  if (url.includes("/api/v1/academics/scope")) return json(SCOPE);
  if (url.includes("/api/v1/academics/levels")) return json(LEVELS);
  if (url.includes("/api/v1/academics/curriculum-profiles")) return json(PROFILES);
  if (url.includes("/api/v1/academics/academic-years")) return json(YEARS);
  if (url.includes("/api/v1/academics/subjects")) return json(SUBJECTS);
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

describe("academics panels", () => {
  it("creates a subject and replaces a level's subject assignments", async () => {
    let created: Record<string, unknown> | null = null;
    let assignments: Record<string, unknown> | null = null;
    stubAcademics(["academics.view", "academics.manage"], (request) => {
      const { url, method } = request;
      if (method === "POST" && url.endsWith("/api/v1/academics/subjects")) {
        created = request.body;
        return json(subject({ id: "sub-geo", code: "geo", name: "Geography" }), 201);
      }
      if (method === "PUT" && /\/levels\/[^/]+\/subjects$/.test(url)) {
        assignments = request.body;
        return json({
          level_id: "lvl-1",
          level_code: "grade-1",
          items: [{ subject_id: "sub-math", code: "math", name: "Mathematics", name_am: null, credit: 1, is_active: true }],
          total: 1,
        });
      }
      if (/\/levels\/[^/]+\/subjects$/.test(url)) {
        return json({ level_id: "lvl-1", level_code: "grade-1", items: [], total: 0 });
      }
      if (url.includes("/api/v1/academics/subject-groups")) return json({ items: [], total: 0 });
      if (url.includes("/api/v1/academics/subjects")) return json(SUBJECTS);
      return baseRoutes(request);
    });
    renderAcademics();

    fireEvent.click(await screen.findByTestId("academics-tab-subjects"));
    fireEvent.change(await screen.findByTestId("subject-code"), { target: { value: "geo" } });
    fireEvent.change(screen.getByTestId("subject-name"), { target: { value: "Geography" } });
    fireEvent.click(screen.getByRole("button", { name: "Add subject" }));
    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toEqual({ code: "geo", name: "Geography", name_am: null });

    fireEvent.change(screen.getByTestId("subject-level"), { target: { value: "lvl-1" } });
    const math = await screen.findByTestId("assign-math");
    fireEvent.click(math);
    fireEvent.click(screen.getByRole("button", { name: "Save subjects" }));

    await waitFor(() => expect(assignments).not.toBeNull());
    expect(assignments).toEqual({ subjects: [{ subject_id: "sub-math", credit: 1 }] });
  });

  it("creates and softly deletes a section", async () => {
    const posts: Record<string, unknown>[] = [];
    let deleted: string | null = null;
    stubAcademics(["academics.view", "academics.manage"], (request) => {
      const { url, method } = request;
      if (method === "DELETE" && url.includes("/api/v1/academics/sections/")) {
        deleted = url;
        return json(null, 204);
      }
      if (method === "POST" && url.endsWith("/api/v1/academics/sections")) {
        posts.push(request.body ?? {});
        return json(section(), 201);
      }
      if (url.includes("/api/v1/academics/sections")) return json({ items: [section()], total: 1 });
      return baseRoutes(request);
    });
    renderAcademics();

    fireEvent.click(await screen.findByTestId("academics-tab-sections"));
    await waitFor(() =>
      expect((screen.getByTestId("section-year") as HTMLSelectElement).value).toBe("year-1"),
    );
    const levelSelect = screen.getByTestId("section-level") as HTMLSelectElement;
    await waitFor(() => expect(levelSelect.options.length).toBeGreaterThan(1));
    fireEvent.change(levelSelect, { target: { value: "lvl-1" } });
    fireEvent.change(screen.getByTestId("section-code"), { target: { value: "B" } });
    fireEvent.change(screen.getByTestId("section-capacity"), { target: { value: "35" } });
    fireEvent.click(screen.getByRole("button", { name: "Add section" }));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]).toEqual({
      year_id: "year-1",
      level_id: "lvl-1",
      code: "B",
      name: null,
      name_am: null,
      capacity: 35,
      homeroom_user_id: null,
    });

    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => expect(deleted).not.toBeNull());
    expect(deleted).toContain("/api/v1/academics/sections/sec-1");
  });

  it("previews then applies a curriculum profile to a year", async () => {
    const posted: { url: string; body: Record<string, unknown> | null }[] = [];
    stubAcademics(["academics.view", "academics.manage"], (request) => {
      const { url, method } = request;
      if (method === "POST" && url.endsWith("/curriculum-profiles/profile-1/apply")) {
        posted.push({ url, body: request.body });
        return json(applyResult({ applied: request.body?.confirm === true }));
      }
      return baseRoutes(request);
    });
    renderAcademics();

    fireEvent.click(await screen.findByTestId("academics-tab-curriculum"));
    expect(await screen.findByTestId("profile-national")).toBeInTheDocument();
    await waitFor(() =>
      expect((screen.getByTestId("profile-apply-year") as HTMLSelectElement).value).toBe("year-1"),
    );

    fireEvent.click(screen.getByTestId("profile-preview"));
    expect(await screen.findByTestId("profile-preview-result")).toHaveTextContent(
      "Term systems match.",
    );
    expect(screen.getByTestId("profile-preview-result")).toHaveTextContent("2 levels change");

    fireEvent.click(screen.getByTestId("profile-apply"));
    await waitFor(() => expect(posted).toHaveLength(2));
    expect(posted[0].body).toEqual({ year_id: "year-1", confirm: false });
    expect(posted[1].body).toEqual({ year_id: "year-1", confirm: true });
    expect(await screen.findByText("Applied")).toBeInTheDocument();
  });

  it("blocks a mismatched term system before apply", async () => {
    stubAcademics(["academics.view", "academics.manage"], (request) => {
      const { url, method } = request;
      if (method === "POST" && url.endsWith("/curriculum-profiles/profile-1/apply")) {
        return json(
          applyResult({
            term_system_matches: false,
            profile_term_system: "quarter",
            year_term_system: "semester",
            levels_changed: 0,
            assignments_added: 0,
            assignments_removed: 0,
          }),
        );
      }
      return baseRoutes(request);
    });
    renderAcademics();

    fireEvent.click(await screen.findByTestId("academics-tab-curriculum"));
    await screen.findByTestId("profile-national");
    await waitFor(() =>
      expect((screen.getByTestId("profile-apply-year") as HTMLSelectElement).value).toBe("year-1"),
    );

    fireEvent.click(screen.getByTestId("profile-preview"));
    expect(await screen.findByTestId("profile-preview-result")).toHaveTextContent(
      "Term systems do not match.",
    );
    expect(screen.getByTestId("profile-apply")).toBeDisabled();
  });
});
