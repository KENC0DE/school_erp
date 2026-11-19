import {
  fromMicro,
  toMicro,
  type MarkDraft,
  type ScoreItem,
  type ScoreStatus,
} from "./types";

/** Keyboard shortcuts shared with the web grid: A absent, E excused, X exempt, − not taken. */
export function statusFromKey(key: string): ScoreStatus | null {
  if (key === "a" || key === "A") return "absent";
  if (key === "e" || key === "E") return "excused";
  if (key === "x" || key === "X") return "exempt";
  if (key === "-" || key === "\u2013") return "not_taken";
  return null;
}

/**
 * Parses what a teacher typed into one mark field. A decimal mark or a blank
 * clears the mark; everything else is rejected instead of being coerced.
 */
export function parseMarkInput(text: string): MarkDraft | null {
  const value = text.trim();
  if (value === "") return { raw: "", status: "present" };
  if (!/^\d+(?:\.\d{1,6})?$/.test(value)) return null;
  return { raw: value, status: "present" };
}

export function isOverMax(
  raw: string,
  outOf: string,
  allowBonus: boolean,
): boolean {
  if (!raw.trim()) return false;
  const value = toMicro(raw);
  const maximum = toMicro(outOf);
  if (value === null || maximum === null) return false;
  return !allowBonus && value > maximum;
}

/** Scales a raw mark to the component maximum with the backend's rounding. */
export function previewConverted(
  raw: string,
  outOf: string,
  componentMax: string,
  precision = 2,
): string | null {
  const value = toMicro(raw);
  const maximum = toMicro(outOf);
  const component = toMicro(componentMax);
  if (
    value === null ||
    maximum === null ||
    component === null ||
    maximum === 0n
  )
    return null;
  const micro = (value * component) / maximum;
  const unit = 10n ** BigInt(6 - Math.max(0, Math.min(6, precision)));
  const rounded = ((micro + unit / 2n) / unit) * unit;
  return fromMicro(rounded);
}

/** The converted value shown under a row; a status or an empty mark shows none. */
export function displayConverted(
  draft: MarkDraft,
  outOf: string,
  componentMax: string,
): string | null {
  if (draft.status !== "present") return null;
  const raw = draft.raw.trim();
  if (raw === "") return null;
  return previewConverted(raw, outOf, componentMax);
}

export function markKey(assessmentId: string, studentId: string): string {
  return `${assessmentId}:${studentId}`;
}

/** Index of the row that auto-advance moves to, clamped to the list. */
export function nextRowIndex(count: number, current: number): number {
  if (count <= 0) return 0;
  return Math.min(current + 1, count - 1);
}

/** Whether a draft would actually change the stored mark. */
export function isChanged(
  draft: MarkDraft,
  item: ScoreItem | undefined,
): boolean {
  if (item === undefined)
    return draft.status !== "present" || draft.raw.trim() !== "";
  const raw = draft.status === "present" ? draft.raw.trim() : "";
  const savedRaw = item.status === "present" ? (item.raw_score ?? "") : "";
  return draft.status !== item.status || raw !== savedRaw;
}

/** The request value for a draft: a status carries no raw mark. */
export function requestValue(draft: MarkDraft): {
  raw_score: string | null;
  status: ScoreStatus;
} {
  if (draft.status !== "present")
    return { raw_score: null, status: draft.status };
  return {
    raw_score: draft.raw.trim() === "" ? null : draft.raw.trim(),
    status: "present",
  };
}
