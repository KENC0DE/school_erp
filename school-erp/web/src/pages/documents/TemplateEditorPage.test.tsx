import type { Layout } from "@erp/documents";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fieldsResponse,
  json,
  renderDocuments,
  stubDocuments,
  template,
  version,
  type MockRequest,
} from "./testing";

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

function editorHandler(
  overrides: (request: MockRequest) => Response | null = () => null,
) {
  return (request: MockRequest) => {
    const custom = overrides(request);
    if (custom) return custom;
    if (request.url.endsWith("/api/v1/documents/fields")) return json(fieldsResponse());
    if (request.url.endsWith("/api/v1/documents/templates/tpl-1/versions/ver-1")) {
      return json(version());
    }
    if (request.url.endsWith("/api/v1/documents/templates/tpl-1")) return json(template());
    return json({ error: { code: "NOT_FOUND", message: "not found" } }, 404);
  };
}

describe("document canvas editor", () => {
  it("adds a text element, inserts a field, saves the layout and previews sample data", async () => {
    const patches: MockRequest[] = [];
    stubDocuments(
      ["*"],
      editorHandler((request) => {
        if (request.method === "PATCH") {
          patches.push(request);
          return json(
            version({
              row_version: 2,
              layout: request.body?.layout as Layout,
            }),
          );
        }
        return null;
      }),
    );
    renderDocuments("/documents/tpl-1");

    expect(await screen.findByTestId("template-editor")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("add-text"));
    expect(screen.getByTestId("inspector-text")).toHaveValue("New text");

    fireEvent.click(screen.getByTestId("field-student.full_name"));
    expect(screen.getByTestId("inspector-text")).toHaveValue("New text {{student.full_name}}");

    fireEvent.click(screen.getByTestId("editor-save"));
    await waitFor(() => expect(patches).toHaveLength(1));
    const layout = patches[0].body?.layout as Layout;
    expect(layout.elements).toHaveLength(1);
    expect((layout.elements[0] as { content: string }).content).toBe(
      "New text {{student.full_name}}",
    );
    expect(patches[0].body?.row_version).toBe(1);
    expect(await screen.findByTestId("editor-notice")).toHaveTextContent("The draft was saved.");

    fireEvent.click(screen.getByTestId("editor-preview"));
    const preview = await screen.findByTestId("preview-page");
    expect(within(preview).getByText("New text Abebe Kebede Tadesse")).toBeInTheDocument();
    expect(screen.getByTestId("editor-save-state")).toHaveTextContent("All changes saved");
  });

  it("undoes and redoes an inserted element", async () => {
    stubDocuments(["*"], editorHandler());
    renderDocuments("/documents/tpl-1");

    await screen.findByTestId("template-editor");
    expect(screen.queryByTestId("doc-selection")).toBeNull();
    fireEvent.click(screen.getByTestId("add-shape"));
    expect(screen.getByTestId("doc-selection")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("editor-undo"));
    await waitFor(() => expect(screen.queryByTestId("doc-selection")).toBeNull());
    expect(screen.getByTestId("editor-undo")).toBeDisabled();

    fireEvent.click(screen.getByTestId("editor-redo"));
    expect(await screen.findByTestId("doc-selection")).toBeInTheDocument();
  });

  it("opens a published version read-only and starts a draft on request", async () => {
    let drafts = 0;
    const published = version({
      id: "ver-pub",
      status: "published",
      published_at: "2026-11-19T10:00:00Z",
    });
    stubDocuments(
      ["*"],
      editorHandler((request) => {
        if (request.method === "POST" && request.url.endsWith("/versions")) {
          drafts += 1;
          return json(version({ id: "ver-2", version_number: 2, status: "draft" }), 201);
        }
        if (request.url.includes("/versions/ver-pub")) return json(published);
        if (request.url.includes("/versions/ver-2")) return json(version({ id: "ver-2", version_number: 2 }));
        if (request.url.endsWith("/api/v1/documents/templates/tpl-1")) {
          return json(
            template({
              draft_version_id: null,
              draft_version_number: null,
              current_version_id: "ver-pub",
            }),
          );
        }
        return null;
      }),
    );
    renderDocuments("/documents/tpl-1");

    expect(await screen.findByTestId("editor-read-only")).toBeInTheDocument();
    expect(screen.getByTestId("editor-start-draft")).toBeInTheDocument();
    expect(screen.getByTestId("add-text")).toBeDisabled();
    fireEvent.click(screen.getByTestId("editor-start-draft"));
    await waitFor(() => expect(drafts).toBe(1));
  });
});
