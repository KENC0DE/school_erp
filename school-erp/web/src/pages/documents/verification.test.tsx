import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { json, renderDocuments, stubDocuments, type MockRequest } from "./testing";

const VERIFY = "/api/v1/documents/public/verify/";

function handler(overrides: (request: MockRequest) => Response | null = () => null) {
  return (request: MockRequest) => {
    const custom = overrides(request);
    if (custom) return custom;
    return json({ error: { code: "NOT_FOUND", message: "not found" } }, 404);
  };
}

function verification(overrides: Record<string, unknown> = {}) {
  return {
    valid: true,
    number: "DOC-2026-00001",
    doc_type: "certificate_completion",
    recipient_name: "Abebe Dawit Samuel",
    issued_at: "2026-11-19T09:01:00Z",
    school_name: "Demo Academy",
    ...overrides,
  };
}

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("public document verification", () => {
  it("confirms a genuine document without a session", async () => {
    const requests: string[] = [];
    stubDocuments(
      ["*"],
      handler((request) => {
        if (request.url.includes(VERIFY)) {
          requests.push(request.url);
          return json(verification());
        }
        return null;
      }),
    );
    renderDocuments("/verify/abc123def456");

    expect(await screen.findByTestId("verify-valid")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByTestId("verify-number")).toHaveTextContent("DOC-2026-00001");
    expect(screen.getByTestId("verify-recipient")).toHaveTextContent("Abebe Dawit Samuel");
    expect(screen.getByText("Certificate of completion")).toBeInTheDocument();
    expect(screen.getByText("Demo Academy")).toBeInTheDocument();
    expect(screen.getByText(/never reveals marks/i)).toBeInTheDocument();
    expect(requests).toHaveLength(1);
    expect(requests[0]).toContain(`${VERIFY}abc123def456`);
  });

  it("shows the neutral not-found state for an unknown code", async () => {
    stubDocuments(
      ["*"],
      handler((request) =>
        request.url.includes(VERIFY)
          ? json(
              {
                error: {
                  code: "NOT_FOUND",
                  message: "This document could not be verified",
                  message_key: "error.documents.verification_not_found",
                },
              },
              404,
            )
          : null,
      ),
    );
    renderDocuments("/verify/not-a-real-code");

    expect(await screen.findByTestId("verify-invalid")).toBeInTheDocument();
    expect(screen.getByText("Document not found")).toBeInTheDocument();
    expect(screen.getByText(/does not match any document/i)).toBeInTheDocument();
  });

  it("offers a retry when verification itself fails", async () => {
    stubDocuments(
      ["*"],
      handler((request) =>
        request.url.includes(VERIFY)
          ? json({ error: { code: "INTERNAL_ERROR", message: "boom" } }, 500)
          : null,
      ),
    );
    renderDocuments("/verify/abc123def456");

    expect(await screen.findByTestId("verify-error")).toBeInTheDocument();
    expect(screen.getByText("Verification unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
