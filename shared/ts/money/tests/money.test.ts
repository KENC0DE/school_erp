import { describe, expect, it } from "vitest";

import { allocate, formatSantim, MoneyError, parseMoney } from "../src";

describe("money", () => {
  it("parses and formats ETB", () => {
    expect(parseMoney("ETB 1,250.50")).toBe(125050);
    expect(parseMoney("ብር 9.99")).toBe(999);
    expect(formatSantim(125050)).toBe("ETB 1,250.50");
    expect(formatSantim(125050, { locale: "am" })).toBe("ብር 1,250.50");
  });

  it("allocates without losing a santim", () => {
    expect(allocate(100, [1, 1, 1]).reduce((a, b) => a + b, 0)).toBe(100);
    expect(allocate(1001, [2, 3, 5]).reduce((a, b) => a + b, 0)).toBe(1001);
  });

  it("rejects bad input", () => {
    expect(() => parseMoney("abc")).toThrow(MoneyError);
    expect(() => formatSantim(1.5)).toThrow(MoneyError);
    expect(() => allocate(10, [0, 0])).toThrow(MoneyError);
  });
});
