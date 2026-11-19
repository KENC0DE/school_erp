import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { issuedList, json, renderDocuments, stubDocuments, type MockRequest } from "./testing";

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function handler(overrides: (request: MockRequest) => Response | null = () => null) {
  return (request: MockRequest) => {
    const custom = overrides(request);
    if (custom) return custom;
    if (request.url.includes("/api/v1/documents/issued?")) return json(issuedList());
    return json({ error: { code: "NOT_FOUND", message: "not found" } }, 404);
  };
}

describe("issued documents", () => {
  it("lists issued documents with their number, recipient and download", async () => {
    stubDocuments(["*"], handler());
    renderDocuments("/documents/issued");

    expect(await screen.findByTestId("issued-list")).toBeInTheDocument();
    expect(screen.getByText("DOC-2026-00001")).toBeInTheDocument();
    expect(screen.getByText("Abebe Dawit Samuel")).toBeInTheDocument();
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByTestId("issued-download-DOC-2026-00001")).toBeInTheDocument();
  });

  it("reprints the stored artifact instead of re-rendering", async () => {
    const clicks: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(this.href);
    });
    const requests: string[] = [];
    stubDocuments(
      ["*"],
      handler((request) => {
        if (request.url.endsWith("/api/v1/documents/issued/issued-1/reprint")) {
          requests.push(request.url);
          return json({
            id: "issued-1",
            number: "DOC-2026-00001",
            file_id: "file-1",
            url: "http://localhost/api/v1/files/content/doc.pdf?expires=1&signature=x",
            checksum_sha256: "abc",
          });
        }
        return null;
      }),
    );
    renderDocuments("/documents/issued");

    fireEvent.click(await screen.findByTestId("issued-reprint-DOC-2026-00001"));
    await waitFor(() => expect(requests).toHaveLength(1));
    expect(await screen.findByTestId("issued-notice")).toHaveTextContent(
      "DOC-2026-00001 is ready to download.",
    );
    expect(clicks[0]).toContain("/api/v1/files/content/doc.pdf");
  });

  it("shows an empty state before the first batch", async () => {
    stubDocuments(
      ["*"],
      handler((request) =>
        request.url.includes("/api/v1/documents/issued?") ? json(issuedList([])) : null,
      ),
    );
    renderDocuments("/documents/issued");
    expect(await screen.findByTestId("issued-empty")).toBeInTheDocument();
  });
});
