export type AttendanceMode = "daily" | "per_period";
export type SessionStatus = "open" | "submitted" | "locked";
export type RecordStatus = "present" | "absent" | "late" | "excused";

export const SESSION_STATUSES: readonly SessionStatus[] = [
  "open",
  "submitted",
  "locked",
];

export const RECORD_STATUSES: readonly RecordStatus[] = [
  "present",
  "absent",
  "late",
  "excused",
];

export interface SessionCounts {
  total: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
}

export interface SessionSummary {
  id: string;
  year_id: string;
  year_code: string;
  section_id: string;
  section_code: string;
  section_name: string | null;
  level_id: string;
  level_code: string;
  level_name: string;
  date: string;
  mode: AttendanceMode;
  period: number | null;
  subject_id: string | null;
  subject_code: string | null;
  subject_name: string | null;
  status: SessionStatus;
  notes: string | null;
  counts: SessionCounts;
  status_changed_at: string | null;
  status_changed_by: string | null;
  status_changed_by_name: string | null;
  row_version: number;
}

export interface RosterEntry {
  student_id: string;
  student_number: string;
  full_name: string;
  roll_number: string | null;
  status: RecordStatus | null;
  record_id: string | null;
}

export interface AttendanceRecord {
  id: string;
  session_id: string;
  student_id: string;
  student_number: string;
  student_name: string;
  student_name_am: string | null;
  roll_number: string | null;
  status: RecordStatus;
  reason: string | null;
  late_minutes: number | null;
  note: string | null;
  recorded_at: string;
  recorded_by: string | null;
  recorded_by_name: string | null;
  row_version: number;
}

export interface SessionDetail extends SessionSummary {
  records: AttendanceRecord[];
  roster: RosterEntry[];
}

export interface SessionList {
  items: SessionSummary[];
  next_cursor: string | null;
  total: number;
}

export interface SessionFilters {
  year_id: string;
  level_id: string;
  section_id: string;
  date: string;
  status: "" | SessionStatus;
}

export interface RecordDraft {
  student_id: string;
  status: RecordStatus;
  reason: string;
  late_minutes: string;
}

export interface RecordInput {
  student_id: string;
  status: RecordStatus;
  reason?: string | null;
  late_minutes?: number | null;
}

export const EMPTY_FILTERS: SessionFilters = {
  year_id: "",
  level_id: "",
  section_id: "",
  date: "",
  status: "",
};

export function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export function draftsFrom(detail: SessionDetail): Record<string, RecordDraft> {
  const drafts: Record<string, RecordDraft> = {};
  for (const entry of detail.roster) {
    const record = detail.records.find((item) => item.student_id === entry.student_id);
    drafts[entry.student_id] = {
      student_id: entry.student_id,
      status: record?.status ?? entry.status ?? "present",
      reason: record?.reason ?? "",
      late_minutes:
        record?.late_minutes === null || record?.late_minutes === undefined
          ? ""
          : String(record.late_minutes),
    };
  }
  return drafts;
}

export function changedRecords(
  detail: SessionDetail,
  drafts: Record<string, RecordDraft>,
): RecordInput[] {
  const byStudent = new Map(
    detail.records.map((record) => [record.student_id, record]),
  );
  const changed: RecordInput[] = [];
  for (const entry of detail.roster) {
    const draft = drafts[entry.student_id];
    if (!draft) continue;
    const current = byStudent.get(entry.student_id);
    const reason = draft.reason.trim();
    const late = draft.late_minutes.trim() === "" ? null : Number(draft.late_minutes);
    const currentReason = current?.reason ?? "";
    const currentLate = current?.late_minutes ?? null;
    if (
      current &&
      current.status === draft.status &&
      currentReason === reason &&
      currentLate === (draft.status === "late" ? late : null)
    ) {
      continue;
    }
    changed.push({
      student_id: entry.student_id,
      status: draft.status,
      reason: reason || null,
      late_minutes: draft.status === "late" ? late : null,
    });
  }
  return changed;
}
