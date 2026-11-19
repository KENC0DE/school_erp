import { fromMicro, toMicro, type ScoreStatus } from "./types";

export interface MarkRow {
  studentId: string;
  studentNumber: string;
  studentName: string;
  rollNumber: string | null;
}

export interface MarkColumn {
  id: string;
  title: string;
  outOf: string;
  componentMax: string;
  allowBonus: boolean;
}

export interface CellValue {
  raw: string;
  status: ScoreStatus;
}

export const STATUS_SHORT: Record<ScoreStatus, string> = {
  present: "",
  absent: "A",
  excused: "E",
  exempt: "X",
  not_taken: "–",
};

/** Keyboard shortcuts for a status, matching ARCH §11.3. */
export function statusFromKey(key: string): ScoreStatus | null {
  if (key === "a" || key === "A") return "absent";
  if (key === "e" || key === "E") return "excused";
  if (key === "x" || key === "X") return "exempt";
  if (key === "-" || key === "\u2013") return "not_taken";
  return null;
}

/** Parse one cell: a decimal mark or a status token. */
export function parseCellToken(token: string): CellValue | null {
  const value = token.trim();
  if (value === "") return { raw: "", status: "present" };
  if (statusFromKey(value) !== null && value.length === 1) {
    return { raw: "", status: statusFromKey(value) as ScoreStatus };
  }
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

/** Scale a raw mark to the component maximum, rounded like the backend. */
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

export function cellKey(assessmentId: string, studentId: string): string {
  return `${assessmentId}:${studentId}`;
}

/** A prepared TSV sheet: student number, name and one column per assessment. */
export function buildTemplate(
  rows: MarkRow[],
  columns: MarkColumn[],
  valueOf: (assessmentId: string, studentId: string) => string,
): string {
  const clean = (value: string) => value.replace(/[\t\r\n]+/g, " ").trim();
  const header = [
    "Student number",
    "Student",
    ...columns.map(
      (column) => `${clean(column.title)} (out of ${column.outOf})`,
    ),
  ];
  const lines = [header.join("\t")];
  for (const row of rows) {
    lines.push(
      [
        row.studentNumber,
        clean(row.studentName),
        ...columns.map((column) => valueOf(column.id, row.studentId)),
      ].join("\t"),
    );
  }
  return `${lines.join("\n")}\n`;
}

export type UploadIssueCode =
  | "unknown_student"
  | "unknown_assessment"
  | "invalid_value"
  | "over_max"
  | "duplicate";

export interface UploadIssue {
  code: UploadIssueCode;
  line: number;
  value: string;
  student?: string;
  assessment?: string;
}

export interface UploadCell {
  assessmentId: string;
  studentId: string;
  raw: string;
  status: ScoreStatus;
}

export interface UploadPreview {
  cells: UploadCell[];
  issues: UploadIssue[];
  matchedStudents: number;
}

function splitDelimited(text: string): { delimiter: string; rows: string[][] } {
  const body = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const delimiter = body.includes("\t") ? "\t" : ",";
  const rows = body
    .split("\n")
    .filter((line) => line.trim() !== "")
    .map((line) => line.split(delimiter).map((cell) => cell.trim()));
  return { delimiter, rows };
}

function headerTitle(header: string): string {
  return header.replace(/\s*\(out of[^)]*\)\s*$/i, "").trim();
}

/** Validate an uploaded/pasted sheet against the loaded grid before committing. */
export function parseUpload(
  text: string,
  rows: MarkRow[],
  columns: MarkColumn[],
  allowBonusOf: (assessmentId: string) => boolean,
): UploadPreview {
  const { rows: table } = splitDelimited(text);
  const issues: UploadIssue[] = [];
  const cells: UploadCell[] = [];
  const seen = new Set<string>();
  const students = new Map(rows.map((row) => [row.studentNumber, row]));
  const columnByTitle = new Map(
    columns.map((column) => [column.title, column]),
  );

  if (table.length === 0) {
    return {
      cells,
      issues: [{ code: "invalid_value", line: 1, value: "" }],
      matchedStudents: 0,
    };
  }

  const header = table[0];
  const mapped: { index: number; column: MarkColumn }[] = [];
  header.slice(2).forEach((cell, offset) => {
    const column = columnByTitle.get(headerTitle(cell));
    if (column === undefined) {
      issues.push({ code: "unknown_assessment", line: 1, value: cell });
      return;
    }
    mapped.push({ index: offset + 2, column });
  });

  const matched = new Set<string>();
  const applied = new Set<string>();
  table.slice(1).forEach((line, rowIndex) => {
    const lineNumber = rowIndex + 2;
    const student = students.get(line[0] ?? "");
    if (student === undefined) {
      issues.push({
        code: "unknown_student",
        line: lineNumber,
        value: line[0] ?? "",
      });
      return;
    }
    matched.add(student.studentId);
    for (const { index, column } of mapped) {
      const token = line[index] ?? "";
      if (token === "") continue;
      const parsed = parseCellToken(token);
      if (parsed === null) {
        issues.push({
          code: "invalid_value",
          line: lineNumber,
          value: token,
          student: student.studentNumber,
          assessment: column.title,
        });
        continue;
      }
      if (
        parsed.status === "present" &&
        isOverMax(parsed.raw, column.outOf, allowBonusOf(column.id))
      ) {
        issues.push({
          code: "over_max",
          line: lineNumber,
          value: token,
          student: student.studentNumber,
          assessment: column.title,
        });
        continue;
      }
      const key = cellKey(column.id, student.studentId);
      if (seen.has(key)) {
        issues.push({
          code: "duplicate",
          line: lineNumber,
          value: token,
          student: student.studentNumber,
          assessment: column.title,
        });
        continue;
      }
      seen.add(key);
      applied.add(student.studentId);
      cells.push({
        assessmentId: column.id,
        studentId: student.studentId,
        raw: parsed.raw,
        status: parsed.status,
      });
    }
  });

  return { cells, issues, matchedStudents: applied.size };
}

/** Split a pasted block into trimmed tokens, dropping one trailing empty line. */
export function parsePasteBlock(text: string): string[][] {
  const body = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const lines = body.split("\n");
  if (lines.length > 0 && lines[lines.length - 1].trim() === "") lines.pop();
  return lines.map((line) => line.split("\t").map((cell) => cell.trim()));
}
