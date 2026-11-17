/**
 * Ethiopian calendar display layer.
 *
 * Storage is always Gregorian ISO. The full EC <-> GC conversion, Amharic month
 * names and the dual date picker are implemented in P1-15 with authoritative test
 * vectors. Until then these functions make the contract explicit and never
 * pretend to convert.
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

export function formatGregorian(date: Date, locale = "en"): string {
  return new Intl.DateTimeFormat(locale === "am" ? "am-ET" : "en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(date);
}

export function formatEthiopian(date: EthiopianDate, locale = "en"): string {
  const months = locale === "am" ? ETHIOPIAN_MONTHS_AM : ETHIOPIAN_MONTHS_EN;
  return `${months[date.month - 1] ?? date.month} ${date.day}, ${date.year}`;
}

export function notImplemented(): never {
  throw new Error("Ethiopian calendar conversion lands in P1-15");
}
