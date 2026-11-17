import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { setToken } from "../lib/storage";
import { handleAuth, installFetch, jsonBody, notFound, SCHOOL } from "../test/mockApi";

const SESSION = {
  token: "session-token-123",
  expires_at: "2026-11-17T18:00:00+00:00",
  read_only: false,
  reason: "Fixing the demo school",
  instance_id: "s1",
};

describe("SupportSessionDialog", () => {
  beforeEach(() => {
    localStorage.clear();
    setToken("token");
    window.history.pushState({}, "", "/schools/s1");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function renderDialogFixture() {
    return installFetch((url, init) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      if (url.endsWith("/controller/v1/schools/s1/support-session") && init.method === "POST") {
        return { body: SESSION };
      }
      if (url.endsWith("/controller/v1/schools/s1")) return { body: SCHOOL };
      return notFound(url);
    });
  }

  it("requires a reason of at least four characters before submitting", async () => {
    renderDialogFixture();
    render(<App />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Open as school admin" }),
    );

    const dialog = screen.getByRole("dialog", { name: "Open as school admin" });
    const submit = within(dialog).getByTestId("support-submit");
    const reason = within(dialog).getByLabelText("Reason for access");

    expect(submit).toBeDisabled();

    fireEvent.change(reason, { target: { value: "Fix" } });
    expect(submit).toBeDisabled();

    fireEvent.change(reason, { target: { value: "Fixing the demo school" } });
    expect(submit).toBeEnabled();
  });

  it("posts the reason and opens the school's controller-login URL in a new tab", async () => {
    const fetchMock = renderDialogFixture();
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Open as school admin" }));
    const dialog = screen.getByRole("dialog", { name: "Open as school admin" });
    fireEvent.change(within(dialog).getByLabelText("Reason for access"), {
      target: { value: "Fixing the demo school" },
    });
    fireEvent.click(within(dialog).getByTestId("support-submit"));

    const postCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/controller/v1/schools/s1/support-session") &&
          (init as RequestInit)?.method === "POST",
      );
      expect(call).toBeDefined();
      return call;
    });

    expect(jsonBody(postCall?.[1] as RequestInit)).toEqual({
      reason: "Fixing the demo school",
      read_only: false,
    });

    expect(await screen.findByTestId("support-token")).toHaveTextContent("session-token-123");
    expect(screen.getByTestId("support-expires")).toBeInTheDocument();

    await waitFor(() => expect(openSpy).toHaveBeenCalledTimes(1));
    const openedUrl = String(openSpy.mock.calls[0][0]);
    expect(openedUrl).toContain("http://localhost:5173/controller-login?");
    expect(openedUrl).toContain("token=session-token-123");
    expect(openSpy.mock.calls[0][1]).toBe("_blank");
  });

  it("shows the server error when the support session is refused", async () => {
    installFetch((url, init) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      if (url.endsWith("/controller/v1/schools/s1/support-session") && init.method === "POST") {
        return {
          status: 403,
          body: { error: { code: "FORBIDDEN", message: "Your role cannot open support sessions" } },
        };
      }
      if (url.endsWith("/controller/v1/schools/s1")) return { body: SCHOOL };
      return notFound(url);
    });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Open as school admin" }));
    const dialog = screen.getByRole("dialog", { name: "Open as school admin" });
    fireEvent.change(within(dialog).getByLabelText("Reason for access"), {
      target: { value: "Fixing the demo school" },
    });
    fireEvent.click(within(dialog).getByTestId("support-submit"));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Your role cannot open support sessions",
    );
  });
});
