/**
 * Ethiopian (Amete Mihret) <-> Gregorian calendar conversion.
 *
 * Storage is always Gregorian ISO. This package is the only place that converts
 * for display and pickers. The JDN epoch and leap rule follow the standard
 * arithmetic used by the Ethiopian Calendar (Beyene/Kudlek/Rath):
 *   JDN = 1723856 + 365*year + floor(year/4) + 30*month + day - 31
 * Ethiopian year Y is leap when Y % 4 === 3 (Pagume has six days).
 */

export interface EthiopianDate {
  year: number;
  month: number;
  day: number;
}

export type CalendarPreference = "ethiopian" | "gregorian" | "both";

export const ETHIOPIAN_MONTHS_AM = [
  "መስከረም",
  "ጥቅምት",
  "ኅዳር",
  "ታኅሣሥ",
  "ጥር",
  "የካቲት",
  "መጋቢት",
  "ሚያዝያ",
  "ግንቦት",
  "ሰኔ",
  "ሐምሌ",
  "ነሐሴ",
  "ጳጉሜ",
] as const;

export const ETHIOPIAN_MONTHS_EN = [
  "Meskerem",
  "Tikimt",
  "Hidar",
  "Tahsas",
  "Tir",
  "Yekatit",
  "Megabit",
  "Miazia",
  "Ginbot",
  "Sene",
  "Hamle",
  "Nehase",
  "Pagume",
] as const;

const ETHIOPIAN_EPOCH_JDN = 1723856;
const UNIX_EPOCH_JDN = 2440588;
const MS_PER_DAY = 86_400_000;

export function isEthiopianLeapYear(year: number): boolean {
  return year % 4 === 3;
}

export function daysInEthiopianMonth(year: number, month: number): number {
  if (month < 1 || month > 13) return 0;
  if (month === 13) return isEthiopianLeapYear(year) ? 6 : 5;
  return 30;
}

export function ethiopianToJdn(date: EthiopianDate): number {
  const { year, month, day } = date;
  return (
    ETHIOPIAN_EPOCH_JDN +
    365 * year +
    Math.floor(year / 4) +
    30 * month +
    day -
    31
  );
}

export function jdnToEthiopian(jdn: number): EthiopianDate {
  const offset = jdn - ETHIOPIAN_EPOCH_JDN;
  const cycle = Math.floor(offset / 1461);
  const remainder = ((offset % 1461) + 1461) % 1461;
  const weekdayShift = remainder % 365;
  const leapAdjustment = Math.floor(remainder / 1460);
  const n = weekdayShift + 365 * leapAdjustment;
  return {
    year: 4 * cycle + Math.floor(remainder / 365) - leapAdjustment,
    month: Math.floor(n / 30) + 1,
    day: (n % 30) + 1,
  };
}

/** Gregorian UTC date -> Julian Day Number. */
export function gregorianToJdn(date: Date): number {
  const midnight = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
  return Math.floor(midnight / MS_PER_DAY) + UNIX_EPOCH_JDN;
}

export function jdnToGregorian(jdn: number): Date {
  return new Date((jdn - UNIX_EPOCH_JDN) * MS_PER_DAY);
}

export function ethiopianToGregorian(date: EthiopianDate): Date {
  return jdnToGregorian(ethiopianToJdn(date));
}

export function gregorianToEthiopian(date: Date): EthiopianDate {
  return jdnToEthiopian(gregorianToJdn(date));
}

export function formatEthiopian(date: EthiopianDate, locale = "en"): string {
  const months = locale === "am" ? ETHIOPIAN_MONTHS_AM : ETHIOPIAN_MONTHS_EN;
  const month = months[date.month - 1];
  if (!month) return `${date.day}/${date.month}/${date.year}`;
  return locale === "am"
    ? `${month} ${date.day}፣ ${date.year}`
    : `${month} ${date.day}, ${date.year}`;
}

export function formatGregorian(date: Date, locale = "en"): string {
  return new Intl.DateTimeFormat(locale === "am" ? "am-ET" : "en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    timeZone: "UTC",
  }).format(date);
}

export function formatDual(
  date: Date,
  preference: CalendarPreference,
  locale = "en",
): string {
  const gregorian = formatGregorian(date, locale);
  const ethiopian = formatEthiopian(gregorianToEthiopian(date), locale);
  if (preference === "gregorian") return gregorian;
  if (preference === "ethiopian") return ethiopian;
  return `${ethiopian} (${gregorian})`;
}

/** ISO date (YYYY-MM-DD) for storage, always Gregorian. */
export function toIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function parseIsoDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
