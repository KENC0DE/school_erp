import { describe, expect, it } from "vitest";

import { ModuleRegistry } from "../src";

describe("module registry", () => {
  it("registers modules and filters navigation by enabled + permitted", () => {
    const registry = new ModuleRegistry();
    registry.register({
      key: "sample",
      name: "Sample",
      version: "0.1.0",
      nav: [
        { key: "sample", labelKey: "sample.nav", path: "/sample", permission: "sample.notes.view", order: 10 },
        { key: "admin", labelKey: "sample.admin", path: "/sample/admin", permission: "sample.notes.create", order: 20 },
      ],
      routes: [],
    });
    expect(registry.navFor([], new Set()).length).toBe(0);
    expect(registry.navFor(["sample"], new Set(["sample.notes.view"])).map((i) => i.key)).toEqual(["sample"]);
  });

  it("rejects duplicate module keys", () => {
    const registry = new ModuleRegistry();
    const manifest = { key: "x", name: "X", version: "1", nav: [], routes: [] };
    registry.register(manifest);
    expect(() => registry.register(manifest)).toThrow(/Duplicate/);
  });
});
