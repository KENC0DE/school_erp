import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fieldsResponse,
  json,
  renderDocuments,
  starters,
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

function listHandler(overrides: (request: MockRequest) => Response | null = () => null) {
  return (request: MockRequest) => {
    const custom = overrides(request);
    if (custom) return custom;
    if (request.url.endsWith("/api/v1/documents/templates/starters")) return json(starters());
    if (request.url.endsWith("/api/v1/documents/fields")) return json(fieldsResponse());
    if (request.url.includes("/api/v1/documents/templates?")) {
      return json({ items: [], total: 0 });
    }
    return json({ error: { code: "NOT_FOUND", message: "not found" } }, 404);
  };
}

describe("document template library", () => {
  it("shows an empty state and creates a template from a starter", async () => {
    const posts: MockRequest[] = [];
    stubDocuments(
      ["*"],
      listHandler((request) => {
        if (request.method === "POST" && request.url.endsWith("/api/v1/documents/templates")) {
          posts.push(request);
          return json(template(), 201);
        }
        if (request.url.endsWith("/api/v1/documents/templates/tpl-1")) return json(template());
        if (request.url.endsWith("/api/v1/documents/templates/tpl-1/versions/ver-1")) {
          return json({ ...template().versions[0], template_id: "tpl-1", layout: { version: 1 } });
        }
        return null;
      }),
    );
    renderDocuments();

    expect(await screen.findByTestId("documents-empty")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("template-new"));
    fireEvent.change(await screen.findByTestId("template-name"), {
      target: { value: "Grade 6 certificate" },
    });
    fireEvent.change(screen.getByTestId("template-starter"), {
      target: { value: "certificate_completion" },
    });
    fireEvent.click(screen.getByTestId("template-create"));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body).toEqual({
      name: "Grade 6 certificate",
      starter: "certificate_completion",
    });
  });

  it("lists templates with type labels and deletes one after confirmation", async () => {
    let deleted = false;
    const deletes: string[] = [];
    const existing = template({ id: "tpl-9", key: "report-card", name: "Term report card" });
    stubDocuments(
      ["*"],
      listHandler((request) => {
        if (request.url.includes("/api/v1/documents/templates?")) {
          return json({ items: deleted ? [] : [existing], total: deleted ? 0 : 1 });
        }
        if (request.method === "DELETE" && request.url.endsWith("/api/v1/documents/templates/tpl-9")) {
          deletes.push(request.url);
          deleted = true;
          return json({ id: "tpl-9", key: "report-card", deleted: true, versions_deleted: 1 });
        }
        return null;
      }),
    );
    renderDocuments();

    expect(await screen.findByText("Term report card")).toBeInTheDocument();
    expect(screen.getByText("Report card")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Delete"));
    fireEvent.click(screen.getByTestId("template-delete-confirm"));

    await waitFor(() => expect(deletes).toHaveLength(1));
    expect(await screen.findByTestId("documents-notice")).toHaveTextContent("Template deleted");
  });

  it("denies the studio without the design permission", async () => {
    stubDocuments(["students.view"], listHandler());
    renderDocuments();
    expect(await screen.findByTestId("documents-permission")).toHaveTextContent(
      "You do not have permission to do that",
    );
  });
});
