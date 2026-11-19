import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { App } from "../App";
import { getToken } from "../lib/storage";
import { installFetch, jsonBody, notFound, OWNER } from "../test/mockApi";

function go(path: string) {
  window.history.pushState({}, "", path);
}

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    go("/login");
  });

  it("posts the credentials and stores the access token", async () => {
    const fetchMock = installFetch((url) => {
      if (url.endsWith("/controller/v1/auth/login")) {
        return {
          body: { access_token: "test-token", token_type: "bearer", user: OWNER },
        };
      }
      if (url.endsWith("/controller/v1/schools")) {
        return { body: { items: [], next_cursor: null } };
      }
      return notFound(url);
    });

    render(<App />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "owner@controller.local" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "DevPass#2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(getToken()).toBe("test-token"));
    expect(await screen.findByRole("heading", { name: "Schools" })).toBeInTheDocument();

    const loginCall = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/controller/v1/auth/login"),
    );
    expect(loginCall).toBeDefined();
    expect(loginCall?.[1]?.method).toBe("POST");
    expect(jsonBody(loginCall?.[1] as RequestInit)).toEqual({
      email: "owner@controller.local",
      password: "DevPass#2026",
    });
  });

  it("shows the server error and stores no token on invalid credentials", async () => {
    installFetch((url) => {
      if (url.endsWith("/controller/v1/auth/login")) {
        return {
          status: 401,
          body: { error: { code: "UNAUTHORIZED", message: "Email or password is incorrect" } },
        };
      }
      return notFound(url);
    });

    render(<App />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "owner@controller.local" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email or password is incorrect",
    );
    expect(getToken()).toBeNull();
    expect(screen.getByRole("heading", { name: "Controller sign in" })).toBeInTheDocument();
  });
});
