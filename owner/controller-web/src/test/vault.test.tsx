import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { App } from "../App";
import { setToken } from "../lib/storage";
import { handleAuth, installFetch, notFound, SCHOOL, SECOND_SCHOOL } from "../test/mockApi";

const BROKEN_ENTRY = {
  id: "v1",
  school_id: "s1",
  school_name: "Demo Academy",
  seq: 42,
  action: "fees.invoice.update",
  module: "fees",
  actor_type: "controller",
  actor_id: "u1",
  via: "controller",
  entity_type: "invoice",
  entity_id: "inv-1",
  ts: "2026-11-17T12:00:00+00:00",
  chain_ok: false,
};

const OK_ENTRY = {
  ...BROKEN_ENTRY,
  id: "v2",
  seq: 41,
  via: "web",
  actor_type: "user",
  actor_id: "u9",
  chain_ok: true,
};

describe("VaultPage", () => {
  beforeEach(() => {
    localStorage.clear();
    setToken("token");
    window.history.pushState({}, "", "/vault");
  });

  it("renders audit rows with the via badge and a broken-chain marker", async () => {
    installFetch((url) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      if (url.endsWith("/controller/v1/schools")) {
        return { body: { items: [SCHOOL, SECOND_SCHOOL], next_cursor: null } };
      }
      if (url.includes("/controller/v1/vault?limit=100")) {
        return { body: { items: [BROKEN_ENTRY, OK_ENTRY], next_cursor: null } };
      }
      return notFound(url);
    });

    render(<App />);

    const row = await screen.findByTestId("vault-row-v1");
    expect(within(row).getByText("Demo Academy")).toBeInTheDocument();
    expect(within(row).getByText("42")).toBeInTheDocument();
    expect(within(row).getByText("fees.invoice.update")).toBeInTheDocument();

    const via = within(row).getByTestId("vault-via");
    expect(via).toHaveTextContent("via=controller");
    expect(within(row).getByTestId("vault-chain-broken")).toHaveTextContent("Broken chain");

    const okRow = screen.getByTestId("vault-row-v2");
    expect(within(okRow).getByTestId("vault-via")).toHaveTextContent("via=web");
    expect(within(okRow).getByTestId("vault-chain-ok")).toHaveTextContent("Verified");
  });

  it("refetches the vault when the school filter changes", async () => {
    const seen: string[] = [];
    installFetch((url) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      if (url.endsWith("/controller/v1/schools")) {
        return { body: { items: [SCHOOL, SECOND_SCHOOL], next_cursor: null } };
      }
      if (url.includes("/controller/v1/vault")) {
        seen.push(url);
        return { body: { items: [BROKEN_ENTRY], next_cursor: null } };
      }
      return notFound(url);
    });

    render(<App />);

    await screen.findByTestId("vault-row-v1");
    const filter = screen.getByLabelText("School");
    await screen.findByRole("option", { name: "Second School" });
    fireEvent.change(filter, { target: { value: "s2" } });

    await waitFor(() => expect(seen.some((url) => url.includes("school_id=s2"))).toBe(true));
    expect(seen[0]).toContain("limit=100");
  });

  it("shows an error state when the vault request fails", async () => {
    installFetch((url) => {
      const auth = handleAuth(url);
      if (auth) return auth;
      if (url.endsWith("/controller/v1/schools")) {
        return { body: { items: [SCHOOL], next_cursor: null } };
      }
      if (url.includes("/controller/v1/vault")) {
        return {
          status: 500,
          body: { error: { code: "INTERNAL_ERROR", message: "Vault unavailable" } },
        };
      }
      return notFound(url);
    });

    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Vault unavailable");
  });
});
