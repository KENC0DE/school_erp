import { describe, expect, it } from "vitest";

import {
  ETHIOPIAN_MONTHS_AM,
  ETHIOPIAN_MONTHS_EN,
  daysInEthiopianMonth,
  ethiopianToGregorian,
  formatDual,
  formatEthiopian,
  formatGregorian,
  gregorianToEthiopian,
  isEthiopianLeapYear,
  toIsoDate,
  type EthiopianDate,
} from "../src";

function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

describe("Ethiopian calendar", () => {
  it("exposes thirteen month names in both scripts", () => {
    expect(ETHIOPIAN_MONTHS_AM).toHaveLength(13);
    expect(ETHIOPIAN_MONTHS_EN).toHaveLength(13);
    expect(ETHIOPIAN_MONTHS_AM[0]).toBe("መስከረም");
    expect(ETHIOPIAN_MONTHS_EN[0]).toBe("Meskerem");
  });

  it("matches published new-year and holiday dates", () => {
    // Ethiopian New Year announcements:
    // 1 Meskerem 2016 = 12 Sep 2023; 1 Meskerem 2017 = 11 Sep 2024.
    expect(iso(ethiopianToGregorian({ year: 2016, month: 1, day: 1 }))).toBe("2023-09-12");
    expect(iso(ethiopianToGregorian({ year: 2017, month: 1, day: 1 }))).toBe("2024-09-11");
    // Genna (29 Tahsas 2017) = 7 Jan 2025; Timkat (11 Tir 2017) = 19 Jan 2025.
    // In years after an Ethiopian leap year the same feast falls a day later
    // (Tahsas 29 2016 = 8 Jan 2024), which is why published dates say "7 or 8".
    expect(iso(ethiopianToGregorian({ year: 2017, month: 4, day: 29 }))).toBe("2025-01-07");
    expect(iso(ethiopianToGregorian({ year: 2017, month: 5, day: 11 }))).toBe("2025-01-19");
    expect(gregorianToEthiopian(new Date("2024-09-11T00:00:00Z"))).toEqual({
      year: 2017,
      month: 1,
      day: 1,
    });
    expect(gregorianToEthiopian(new Date("2025-01-07T00:00:00Z"))).toEqual({
      year: 2017,
      month: 4,
      day: 29,
    });
  });

  it("handles leap years and Pagume", () => {
    expect(isEthiopianLeapYear(2015)).toBe(true);
    expect(isEthiopianLeapYear(2016)).toBe(false);
    expect(daysInEthiopianMonth(2015, 13)).toBe(6);
    expect(daysInEthiopianMonth(2016, 13)).toBe(5);
    expect(iso(ethiopianToGregorian({ year: 2015, month: 13, day: 6 }))).toBe("2023-09-11");
    expect(iso(ethiopianToGregorian({ year: 2015, month: 13, day: 7 }))).toBe("2023-09-12");
  });

  it("round-trips every day over 120 Ethiopian years", () => {
    let current = ethiopianToGregorian({ year: 1990, month: 1, day: 1 });
    for (let index = 0; index < 120 * 365 + 30; index += 1) {
      const ethiopian = gregorianToEthiopian(current);
      const back = ethiopianToGregorian(ethiopian);
      expect(iso(back)).toBe(iso(current));
      current = new Date(current.getTime() + 86_400_000);
    }
  });

  it("formats single and dual dates for pickers and documents", () => {
    const date = new Date("2024-09-11T00:00:00Z");
    expect(formatEthiopian({ year: 2017, month: 1, day: 1 })).toBe("Meskerem 1, 2017");
    expect(formatEthiopian({ year: 2017, month: 1, day: 1 }, "am")).toBe("መስከረም 1፣ 2017");
    expect(formatGregorian(date, "en")).toContain("2024");
    expect(formatDual(date, "ethiopian")).toBe("Meskerem 1, 2017");
    expect(formatDual(date, "both", "en")).toContain("Meskerem 1, 2017");
    expect(toIsoDate(date)).toBe("2024-09-11");
  });
});
