import { describe, expect, it } from "vitest";

import {
  CURRENCY,
  MAX_SANTIM,
  MoneyError,
  SANTIM_PER_BIRR,
  add,
  allocate,
  formatSantim,
  parseMoney,
  subtract,
} from "../src";

describe("money", () => {
  it("parses and formats ETB", () => {
    expect(parseMoney("ETB 1,250.50")).toBe(125050);
    expect(parseMoney("ብር 9.99")).toBe(999);
    expect(parseMoney("Br 10")).toBe(1000);
    expect(parseMoney(" 1 250.5 ")).toBe(125050);
    expect(parseMoney(1250)).toBe(125000);
    expect(formatSantim(125050)).toBe("ETB 1,250.50");
    expect(formatSantim(125050, { locale: "am" })).toBe("ብር 1,250.50");
    expect(formatSantim(125050, { withCurrency: false })).toBe("1,250.50");
    expect(CURRENCY).toBe("ETB");
    expect(SANTIM_PER_BIRR).toBe(100);
  });

  it("rounds half a santim up instead of leaking float error", () => {
    expect(parseMoney("1.005")).toBe(101);
    expect(parseMoney("1.004")).toBe(100);
    expect(parseMoney("1.004999")).toBe(100);
    expect(parseMoney("0.005")).toBe(1);
    expect(parseMoney("-1.005")).toBe(-101);
    expect(parseMoney(-1.005)).toBe(-101);
    expect(parseMoney(1.005)).toBe(101);
    expect(parseMoney("0.1")).toBe(10);
    expect(parseMoney("1,250.999")).toBe(125100);
  });

  it("handles large amounts without losing precision", () => {
    expect(parseMoney("9,000,000,000.00")).toBe(900_000_000_000);
    expect(formatSantim(900_000_000_000)).toBe("ETB 9,000,000,000.00");
    expect(formatSantim(MAX_SANTIM)).toBe("ETB 90,071,992,547,409.91");
    expect(add(MAX_SANTIM - 1, 1)).toBe(MAX_SANTIM);
    expect(() => add(MAX_SANTIM, 1)).toThrow(MoneyError);
    expect(() => parseMoney("90,071,992,547,410.00")).toThrow(MoneyError);
    expect(() => formatSantim(MAX_SANTIM + 2)).toThrow(MoneyError);
  });

  it("formats negative amounts and splits them symmetrically", () => {
    expect(formatSantim(-5)).toBe("ETB -0.05");
    expect(formatSantim(-125050, { locale: "am" })).toBe("ብር -1,250.50");
    const negative = allocate(-101, [1, 1, 1]);
    expect(negative.reduce((left, right) => left + right, 0)).toBe(-101);
    expect(negative).toEqual([-34, -34, -33]);
    expect(allocate(101, [1, 1, 1])).toEqual([34, 34, 33]);
  });

  it("adds and subtracts santim", () => {
    expect(add(100, 250, -50)).toBe(300);
    expect(subtract(1000, 999)).toBe(1);
    expect(subtract(0, 500)).toBe(-500);
    expect(() => add(1.5, 1)).toThrow(MoneyError);
    expect(() => subtract(0, 0.25)).toThrow(MoneyError);
  });

  it("allocates without losing a santim", () => {
    expect(allocate(100, [1, 1, 1]).reduce((a, b) => a + b, 0)).toBe(100);
    expect(allocate(1001, [2, 3, 5]).reduce((a, b) => a + b, 0)).toBe(1001);
    expect(allocate(100, [1, 1, 1])).toEqual([34, 33, 33]);
    // Remainder santim go to the largest weight first, ties by input order.
    expect(allocate(10, [1, 2, 3])).toEqual([1, 3, 6]);
    expect(allocate(1, [5, 5])).toEqual([1, 0]);
    expect(allocate(0, [2, 8])).toEqual([0, 0]);
    expect(allocate(7, [1])).toEqual([7]);
  });

  it("rejects bad input", () => {
    expect(() => parseMoney("abc")).toThrow(MoneyError);
    expect(() => parseMoney("")).toThrow(MoneyError);
    expect(() => parseMoney("1.2.3")).toThrow(MoneyError);
    expect(() => parseMoney(Number.NaN)).toThrow(MoneyError);
    expect(() => parseMoney(Number.POSITIVE_INFINITY)).toThrow(MoneyError);
    expect(() => parseMoney(1e21)).toThrow(MoneyError);
    expect(() => formatSantim(1.5)).toThrow(MoneyError);
    expect(() => formatSantim(Number.NaN)).toThrow(MoneyError);
    expect(() => allocate(10, [0, 0])).toThrow(MoneyError);
    expect(() => allocate(10, [])).toThrow(MoneyError);
    expect(() => allocate(10, [-1, 2])).toThrow(MoneyError);
    expect(() => allocate(1.5, [1, 1])).toThrow(MoneyError);
  });
});
