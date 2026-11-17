import { describe, expect, it } from "vitest";

import {
  ETHIOPIAN_MONTHS_AM,
  ETHIOPIAN_MONTHS_EN,
  formatEthiopian,
  formatGregorian,
  notImplemented,
} from "../src";

describe("Ethiopian calendar display layer", () => {
  it("exposes thirteen month names in both scripts", () => {
    expect(ETHIOPIAN_MONTHS_AM).toHaveLength(13);
    expect(ETHIOPIAN_MONTHS_EN).toHaveLength(13);
    expect(ETHIOPIAN_MONTHS_AM[0]).toBe("መስከረም");
    expect(ETHIOPIAN_MONTHS_EN[0]).toBe("Meskerem");
  });

  it("formats an Ethiopian date with the requested script and falls back on bad months", () => {
    expect(formatEthiopian({ year: 2017, month: 1, day: 1 })).toBe("Meskerem 1, 2017");
    expect(formatEthiopian({ year: 2017, month: 1, day: 1 }, "am")).toBe("መስከረም 1, 2017");
    expect(formatEthiopian({ year: 2017, month: 14, day: 1 })).toBe("14 1, 2017");
  });

  it("formats Gregorian dates for the en and am UI", () => {
    const date = new Date(Date.UTC(2026, 10, 17));
    expect(formatGregorian(date, "en")).toMatch(/2026/);
    expect(formatGregorian(date, "am")).toMatch(/2026/);
  });

  it("refuses to fake conversion before P1-15", () => {
    expect(() => notImplemented()).toThrow(/P1-15/);
  });
});
