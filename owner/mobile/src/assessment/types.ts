/** Assessment contracts used by the mobile mark-entry screens (P4-13). */

export type ScoreStatus =
  | "present"
  | "absent"
  | "excused"
  | "exempt"
  | "not_taken";

export const SCORE_STATUSES: readonly ScoreStatus[] = [
  "present",
  "absent",
  "excused",
  "exempt",
  "not_taken",
];

/** Marks are signed integers in millionths, exactly like the backend. */
export const MICRO = 1_000_000n;

export type MarkMode = "card" | "list";

export type SyncState = "saved" | "saving" | "pending" | "error" | "conflict";

export interface AssessmentSummary {
  id: string;
  year_id: string;
  year_code: string;
  term_id: string;
  term_name: string;
  section_id: string;
  section_code: string;
  level_id: string;
  level_name: string;
  subject_id: string;
  subject_name: string;
  component_key: string;
  component_name: string;
  component_max_points: string;
  title: string;
  assessment_date: string;
  out_of: string;
  allow_bonus: boolean;
  status: string;
  scores: number;
  entered: number;
  row_version: number;
}

export interface AssessmentList {
  items: AssessmentSummary[];
  next_cursor: string | null;
  total: number;
}

export interface ScoreItem {
  score_id: string | null;
  student_id: string;
  student_number: string;
  student_name: string;
  student_name_am: string | null;
  roll_number: string | null;
  enrolled: boolean;
  raw_score: string | null;
  out_of: string;
  status: ScoreStatus;
  converted: string | null;
  note: string | null;
  row_version: number | null;
  entered_at: string | null;
}

export interface ScoreStats {
  total: number;
  entered: number;
  missing: number;
  present: number;
  absent: number;
  excused: number;
  exempt: number;
  not_taken: number;
  out_of: string;
  component_max_points: string;
  average_converted: string | null;
  average_percent: string | null;
  highest_converted: string | null;
  lowest_converted: string | null;
}

export interface ScoreSheet {
  assessment_id: string;
  title: string;
  component_key: string;
  component_max_points: string;
  out_of: string;
  allow_bonus: boolean;
  editable: boolean;
  items: ScoreItem[];
  stats: ScoreStats;
}

export interface ScoreInput {
  student_id: string;
  raw_score: string | null;
  status: ScoreStatus;
  row_version: number | null;
}

export interface ScoreBulkResult {
  sheet: ScoreSheet;
  created: number;
  updated: number;
  unchanged: number;
}

export interface MarkingWindow {
  id: string;
  year_id: string;
  term_id: string;
  level_id: string | null;
  section_id: string | null;
  scope_key: string;
  opens_at: string;
  closes_at: string;
  is_active: boolean;
  state: string;
  note: string | null;
  row_version: number;
}

export interface WindowList {
  items: MarkingWindow[];
  next_cursor: string | null;
  total: number;
}

export interface Submission {
  id: string;
  year_id: string;
  term_id: string;
  section_id: string;
  section_code: string;
  subject_id: string;
  subject_name: string;
  status: string;
  submitted_at: string | null;
  approved_at: string | null;
  published_at: string | null;
  locked_at: string | null;
  note: string | null;
  assessments: number;
  scores: number;
  entered: number;
  row_version: number;
}

export interface SubmissionList {
  items: Submission[];
  next_cursor: string | null;
  total: number;
}

/** Short token shown for a non-numeric mark, matching the web grid. */
export const STATUS_SHORT: Record<ScoreStatus, string> = {
  present: "",
  absent: "A",
  excused: "E",
  exempt: "X",
  not_taken: "–",
};

export interface MarkDraft {
  raw: string;
  status: ScoreStatus;
}

export function draftFrom(item: ScoreItem): MarkDraft {
  if (item.status !== "present") return { raw: "", status: item.status };
  return { raw: item.raw_score ?? "", status: "present" };
}

export function toMicro(value: string): bigint | null {
  const trimmed = value.trim();
  if (!/^\d+(\.\d{1,6})?$/.test(trimmed)) return null;
  const [whole = "0", fraction = ""] = trimmed.split(".");
  return BigInt(whole) * MICRO + BigInt((fraction + "000000").slice(0, 6));
}

/** Render micro-units as the shortest exact decimal string. */
export function fromMicro(value: bigint): string {
  const whole = value / MICRO;
  const fraction = (value % MICRO)
    .toString()
    .padStart(6, "0")
    .replace(/0+$/, "");
  return fraction ? `${whole}.${fraction}` : `${whole}`;
}

/** Students are ordered by roll number, then student number. */
export function sortScoreItems(items: ScoreItem[]): ScoreItem[] {
  return [...items].sort((left, right) => {
    const roll = (left.roll_number ?? "").localeCompare(
      right.roll_number ?? "",
      undefined,
      {
        numeric: true,
      },
    );
    return roll !== 0
      ? roll
      : left.student_number.localeCompare(right.student_number);
  });
}
