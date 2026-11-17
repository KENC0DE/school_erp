import { render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../providers/I18nProvider";
import { FileUpload, type UploadedFile } from "./FileUpload";

const messages: Record<string, string> = {
  "files.choose": "Choose a file",
  "files.upload": "Upload",
  "files.uploading": "Uploading…",
  "files.uploaded": "{{name}} uploaded.",
  "files.hint": "Allowed files up to {{max}} MB.",
  "files.error.too_large": "This file is larger than the {{max}} MB limit.",
  "files.error.unsupported": "This file type is not allowed.",
  "files.error.failed": "The file could not be uploaded. Try again.",
};

function uploaded(name = "photo.png"): UploadedFile {
  return {
    id: "file-1",
    name,
    mime: "image/png",
    size_bytes: 12,
    checksum_sha256: "abc",
    url: "/api/v1/files/content/2026/11/photo.png?expires=1&signature=x",
    thumbnail_url: null,
    has_thumbnail: false,
    is_private: true,
    owner_entity_type: "student",
    owner_entity_id: "student-1",
  };
}

function renderUpload(onUploaded = vi.fn()) {
  render(
    <I18nProvider initialMessages={messages}>
      <FileUpload
        onUploaded={onUploaded}
        ownerEntityType="student"
        ownerEntityId="student-1"
        maxBytes={1_000_000}
      />
    </I18nProvider>,
  );
  return onUploaded;
}

describe("FileUpload", () => {
  beforeEach(() => {
    localStorage.setItem("erp.access_token", "test-token");
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("posts multipart form data and reports the uploaded file", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(uploaded()), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onUploaded = renderUpload();
    const file = new File([new Uint8Array([1, 2, 3, 4])], "photo.png", { type: "image/png" });

    fireEvent.change(screen.getByLabelText("Choose a file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(uploaded()));
    expect(await screen.findByText("photo.png uploaded.")).toBeInTheDocument();

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/files");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
    const body = init.body as FormData;
    expect(body.get("file")).toBe(file);
    expect(body.get("is_private")).toBe("true");
    expect(body.get("owner_entity_type")).toBe("student");
    expect(body.get("owner_entity_id")).toBe("student-1");
  });

  it("rejects an oversized file before uploading", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderUpload();
    const file = new File([new Uint8Array(1_000_001)], "big.png", { type: "image/png" });

    fireEvent.change(screen.getByLabelText("Choose a file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This file is larger than the 1 MB limit.",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps a server rejection to a translated message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                code: "VALIDATION_ERROR",
                message_key: "error.file.unsupported_type",
                message: "This file type is not allowed",
              },
            }),
            { status: 415, headers: { "Content-Type": "application/json" } },
          ),
      ),
    );
    renderUpload();
    const file = new File([new Uint8Array([1])], "script.exe", {
      type: "application/octet-stream",
    });

    fireEvent.change(screen.getByLabelText("Choose a file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This file type is not allowed.");
  });
});
