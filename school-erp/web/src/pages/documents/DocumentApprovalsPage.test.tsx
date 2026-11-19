import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  generationBatch,
  json,
  renderDocuments,
  stubDocuments,
  type MockRequest,
} from "./testing";

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-access-token");
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

function pendingBatch(overrides: Record<string, unknown> = {}) {
  return generationBatch({
    status: "pending_approval",
    approval_required: true,
    progress: 0,
    issued_count: 0,
    issued_at: null,
    ...overrides,
  });
}

describe("certificate approvals", () => {
  it("lists a held batch and approves it into the queue", async () => {
    let pending = [pendingBatch()];
    const posts: MockRequest[] = [];
    stubDocuments(["documents.approve"], (request) => {
      if (request.url.includes("/api/v1/documents/generation/approvals")) {
        return json({ items: pending });
      }
      if (
        request.method === "POST" &&
        request.url.endsWith("/api/v1/documents/generation/batches/batch-1/approve")
      ) {
        posts.push(request);
        pending = [];
        return json(generationBatch({ status: "queued", approval_required: true }));
      }
      return json({ items: [], next_cursor: null, total: 0 });
    });

    renderDocuments("/documents/approvals");

    expect(await screen.findByTestId("approvals-list")).toBeInTheDocument();
    expect(screen.getByText("Certificate of completion")).toBeInTheDocument();
    expect(screen.getByText("Requested by Super Admin")).toBeInTheDocument();
    expect(screen.getByText("1 document(s)")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("approval-approve-batch-1"));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body).toEqual({ note: null });
    expect(await screen.findByText("The batch was approved and queued.")).toBeInTheDocument();
    expect(await screen.findByTestId("approvals-empty")).toBeInTheDocument();
  });

  it("requires a reason and rejects the batch", async () => {
    let pending = [pendingBatch()];
    const posts: MockRequest[] = [];
    stubDocuments(["*"], (request) => {
      if (request.url.includes("/api/v1/documents/generation/approvals")) {
        return json({ items: pending });
      }
      if (
        request.method === "POST" &&
        request.url.endsWith("/api/v1/documents/generation/batches/batch-1/reject")
      ) {
        posts.push(request);
        pending = [];
        return json(generationBatch({ status: "rejected", rejection_reason: "Wrong class list" }));
      }
      return json({ items: [], next_cursor: null, total: 0 });
    });

    renderDocuments("/documents/approvals");

    fireEvent.click(await screen.findByTestId("approval-reject-batch-1"));

    fireEvent.click(screen.getByTestId("approvals-confirm-reject"));
    expect(await screen.findByText("Enter a reason of at least 3 characters.")).toBeInTheDocument();
    expect(posts).toHaveLength(0);

    fireEvent.change(screen.getByTestId("approvals-reason"), {
      target: { value: "Wrong class list" },
    });
    fireEvent.click(screen.getByTestId("approvals-confirm-reject"));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body).toEqual({ reason: "Wrong class list" });
    expect(
      await screen.findByText("The batch was rejected; nothing was issued."),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("approvals-empty")).toBeInTheDocument();
  });

  it("hides the queue from users who cannot approve", async () => {
    const called: string[] = [];
    stubDocuments(["documents.template.design"], (request) => {
      called.push(request.url);
      return json({ items: [] });
    });

    renderDocuments("/documents/approvals");

    expect(await screen.findByTestId("approvals-permission")).toHaveTextContent(
      "You do not have permission to do that",
    );
    expect(screen.queryByTestId("approvals-list")).not.toBeInTheDocument();
    expect(called.some((url) => url.includes("/generation/approvals"))).toBe(false);
  });
});
