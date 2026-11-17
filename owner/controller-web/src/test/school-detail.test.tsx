import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { App } from "../App";
import { setToken } from "../lib/storage";
import { handleAuth, installFetch, jsonBody, notFound, SCHOOL } from "../test/mockApi";

describe("SchoolDetailPage", () => {
  beforeEach(() => {
    localStorage.clear();
    setToken("token");
    window.history.pushState({}, "", "/schools/s1");
  });

  it("sends a PATCH with the module key and new state, then reflects it", async () => {
    const fetchMock = installFetch((url, init) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      if (url.endsWith("/controller/v1/schools/s1")) return { body: SCHOOL };
      if (url.endsWith("/controller/v1/schools/s1/modules") && init.method === "PATCH") {
        return {
          body: {
            ...SCHOOL,
            modules: SCHOOL.modules.filter((module) => module !== "sample"),
          },
        };
      }
      return notFound(url);
    });

    render(<App />);

    expect(await screen.findByTestId("school-detail-title")).toHaveTextContent("Demo Academy");

    const sampleToggle = screen.getByRole("switch", { name: "sample module" });
    expect(sampleToggle).toBeChecked();

    fireEvent.click(sampleToggle);

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/controller/v1/schools/s1/modules") &&
          (init as RequestInit)?.method === "PATCH",
      );
      expect(patchCall).toBeDefined();
      expect(jsonBody(patchCall?.[1] as RequestInit)).toEqual({ key: "sample", enabled: false });
    });

    await waitFor(() => expect(sampleToggle).not.toBeChecked());
    expect(screen.getByTestId("module-state-sample")).toHaveTextContent("Off");
    expect(screen.getByTestId("module-state-academics")).toHaveTextContent("On");
  });

  it("rolls the toggle back and shows the error when the PATCH fails", async () => {
    installFetch((url, init) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      if (url.endsWith("/controller/v1/schools/s1/modules") && init.method === "PATCH") {
        return {
          status: 403,
          body: { error: { code: "FORBIDDEN", message: "Your role cannot change modules" } },
        };
      }
      if (url.endsWith("/controller/v1/schools/s1")) return { body: SCHOOL };
      return notFound(url);
    });

    render(<App />);
    const sampleToggle = await screen.findByRole("switch", { name: "sample module" });
    fireEvent.click(sampleToggle);

    expect(await screen.findByRole("alert")).toHaveTextContent("Your role cannot change modules");
    await waitFor(() => expect(sampleToggle).toBeChecked());
  });
});
