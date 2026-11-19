import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fieldsResponse,
  generationBatch,
  generationStaff,
  generationStudents,
  generationTargets,
  json,
  renderDocuments,
  stubDocuments,
  template,
  type MockRequest,
} from "./testing";

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

function handler(overrides: (request: MockRequest) => Response | null = () => null) {
  return (request: MockRequest) => {
    const custom = overrides(request);
    if (custom) return custom;
    if (request.url.endsWith("/api/v1/documents/templates/starters")) {
      return json({ items: [] });
    }
    if (request.url.endsWith("/api/v1/documents/fields")) return json(fieldsResponse());
    if (request.url.includes("/api/v1/documents/templates?")) {
      return json({ items: [template()], total: 1 });
    }
    if (request.url.endsWith("/api/v1/documents/generation/targets")) {
      return json(generationTargets());
    }
    if (request.url.includes("/api/v1/documents/generation/students?")) {
      return json(generationStudents());
    }
    if (request.url.endsWith("/api/v1/documents/generation/batches/batch-1")) {
      return json(generationBatch());
    }
    return json({ error: { code: "NOT_FOUND", message: "not found" } }, 404);
  };
}

describe("document generation dialog", () => {
  it("generates a single document and follows the batch to completion", async () => {
    const posts: MockRequest[] = [];
    stubDocuments(
      ["*"],
      handler((request) => {
        if (request.method === "POST" && request.url.endsWith("/api/v1/documents/generation")) {
          posts.push(request);
          return json(
            { job_id: "job-1", batch_id: "batch-1", count: 1, status: "queued" },
            202,
          );
        }
        return null;
      }),
    );
    renderDocuments();

    fireEvent.click(await screen.findByTestId("template-generate-certificate-completion"));
    expect(await screen.findByTestId("generation-dialog")).toBeInTheDocument();

    const student = await screen.findByTestId("generation-student");
    await waitFor(() => expect(student.querySelectorAll("option")).toHaveLength(2));
    fireEvent.change(student, { target: { value: "stu-1" } });
    fireEvent.click(screen.getByTestId("generation-start"));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body).toEqual({
      template_id: "tpl-1",
      combine: false,
      target: { type: "student", student_id: "stu-1" },
    });

    expect(await screen.findByTestId("generation-progress")).toBeInTheDocument();
    expect(await screen.findByText("Finished")).toBeInTheDocument();
    expect(screen.getByText("1 issued, 0 failed of 1")).toBeInTheDocument();
    expect(screen.getByText("The batch finished. Open an issued document to download or reprint it.")).toBeInTheDocument();
  });

  it("shows a held certificate batch as awaiting approval", async () => {
    stubDocuments(
      ["*"],
      handler((request) => {
        if (request.method === "POST" && request.url.endsWith("/api/v1/documents/generation")) {
          return json(
            { job_id: "job-1", batch_id: "batch-1", count: 1, status: "pending_approval" },
            202,
          );
        }
        if (request.url.endsWith("/api/v1/documents/generation/batches/batch-1")) {
          return json(
            generationBatch({
              status: "pending_approval",
              approval_required: true,
              progress: 0,
              issued_count: 0,
              issued_at: null,
            }),
          );
        }
        return null;
      }),
    );
    renderDocuments();

    fireEvent.click(await screen.findByTestId("template-generate-certificate-completion"));
    const student = await screen.findByTestId("generation-student");
    await waitFor(() => expect(student.querySelectorAll("option")).toHaveLength(2));
    fireEvent.change(student, { target: { value: "stu-1" } });
    fireEvent.click(screen.getByTestId("generation-start"));

    expect(await screen.findByTestId("generation-awaiting-approval")).toHaveTextContent(
      "This certificate batch is waiting for approval before anything is issued.",
    );
    expect(screen.getByText("Awaiting approval")).toBeInTheDocument();
  });

  it("generates an experience letter for a staff member", async () => {
    const posts: MockRequest[] = [];
    stubDocuments(
      ["*"],
      handler((request) => {
        if (request.url.includes("/api/v1/documents/templates?")) {
          return json({
            items: [
              template({
                key: "experience-letter",
                name: "Experience letter",
                doc_type: "experience_letter",
              }),
            ],
            total: 1,
          });
        }
        if (request.url.includes("/api/v1/documents/generation/staff?")) {
          return json(generationStaff());
        }
        if (request.method === "POST" && request.url.endsWith("/api/v1/documents/generation")) {
          posts.push(request);
          return json(
            { job_id: "job-1", batch_id: "batch-1", count: 1, status: "queued" },
            202,
          );
        }
        return null;
      }),
    );
    renderDocuments();

    fireEvent.click(await screen.findByTestId("template-generate-experience-letter"));
    expect(await screen.findByTestId("generation-target-type")).toHaveValue("staff");

    const member = await screen.findByTestId("generation-staff");
    await waitFor(() => expect(member.querySelectorAll("option")).toHaveLength(2));
    expect(member).toHaveTextContent("STF-2026-0001 — Solomon Tesfaye Gebre");
    fireEvent.change(member, { target: { value: "staff-1" } });
    fireEvent.click(screen.getByTestId("generation-start"));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body).toEqual({
      template_id: "tpl-1",
      combine: false,
      target: { type: "staff", staff_id: "staff-1" },
    });
  });

  it("offers section and grade targets from the current year", async () => {
    stubDocuments(["*"], handler());
    renderDocuments();

    fireEvent.click(await screen.findByTestId("template-generate-certificate-completion"));
    fireEvent.change(await screen.findByTestId("generation-target-type"), {
      target: { value: "section" },
    });

    const section = await screen.findByTestId("generation-section");
    await waitFor(() => expect(section.querySelectorAll("option")).toHaveLength(2));
    expect(section).toHaveTextContent("Grade 5 — A");

    fireEvent.change(screen.getByTestId("generation-target-type"), {
      target: { value: "level" },
    });
    const level = await screen.findByTestId("generation-level");
    await waitFor(() => expect(level.querySelectorAll("option")).toHaveLength(2));
    expect(level).toHaveTextContent("Grade 5");
  });
});
