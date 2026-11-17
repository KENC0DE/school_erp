import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { App } from "../App";
import { setToken } from "../lib/storage";
import {
  handleAuth,
  installFetch,
  notFound,
  SCHOOL,
  SECOND_SCHOOL,
} from "../test/mockApi";

describe("SchoolsPage", () => {
  beforeEach(() => {
    localStorage.clear();
    setToken("token");
    window.history.pushState({}, "", "/schools");
  });

  it("renders school rows with status and module information", async () => {
    installFetch((url) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      if (url.endsWith("/controller/v1/schools")) {
        return { body: { items: [SCHOOL, SECOND_SCHOOL], next_cursor: null } };
      }
      return notFound(url);
    });

    render(<App />);

    const row = await screen.findByTestId("school-row-DEMO");
    expect(within(row).getByRole("link", { name: "Demo Academy" })).toHaveAttribute(
      "href",
      "/schools/s1",
    );
    expect(within(row).getByTestId("school-code")).toHaveTextContent("DEMO");
    expect(within(row).getByTestId("school-status-DEMO")).toHaveTextContent("Active");
    expect(within(row).getByText("2 modules")).toBeInTheDocument();
    expect(within(row).getByText("academics")).toBeInTheDocument();
    expect(within(row).getByText("sample")).toBeInTheDocument();
    expect(within(row).getByText("Enrolled")).toBeInTheDocument();

    const second = screen.getByTestId("school-row-DEMO2");
    expect(within(second).getByText("Suspended")).toBeInTheDocument();
    expect(within(second).getByText("1 module")).toBeInTheDocument();
    expect(within(second).getByText("Not enrolled")).toBeInTheDocument();
  });

  it("shows an error with a retry action when the request fails", async () => {
    installFetch((url) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      return {
        status: 500,
        body: { error: { code: "INTERNAL_ERROR", message: "Controller unavailable" } },
      };
    });

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Controller unavailable");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
