import { describe, expect, it } from "vitest";

import {
  buildTemplate,
  isOverMax,
  parseCellToken,
  parsePasteBlock,
  parseUpload,
  previewConverted,
  statusFromKey,
  type MarkColumn,
  type MarkRow,
} from "./marks";

const ROWS: MarkRow[] = [
  {
    studentId: "stu-1",
    studentNumber: "STU-1",
    studentName: "Abel",
    rollNumber: "1",
  },
  {
    studentId: "stu-2",
    studentNumber: "STU-2",
    studentName: "Sara",
    rollNumber: "2",
  },
];

const COLUMNS: MarkColumn[] = [
  {
    id: "exam-1",
    title: "Quiz 1",
    outOf: "15",
    componentMax: "10",
    allowBonus: false,
  },
  {
    id: "exam-2",
    title: "Quiz 2",
    outOf: "20",
    componentMax: "10",
    allowBonus: true,
  },
];

describe("mark entry helpers", () => {
  it("parses numbers and status shortcuts but rejects anything else", () => {
    expect(parseCellToken("12.5")).toEqual({ raw: "12.5", status: "present" });
    expect(parseCellToken("")).toEqual({ raw: "", status: "present" });
    expect(parseCellToken("A")).toEqual({ raw: "", status: "absent" });
    expect(parseCellToken("e")).toEqual({ raw: "", status: "excused" });
    expect(parseCellToken("X")).toEqual({ raw: "", status: "exempt" });
    expect(parseCellToken("-")).toEqual({ raw: "", status: "not_taken" });
    expect(parseCellToken("12,5")).toBeNull();
    expect(parseCellToken("abc")).toBeNull();
    expect(parseCellToken("1.1234567")).toBeNull();
    expect(statusFromKey("z")).toBeNull();
  });

  it("flags a mark above the maximum unless the assessment allows bonus marks", () => {
    expect(isOverMax("15", "15", false)).toBe(false);
    expect(isOverMax("15.5", "15", false)).toBe(true);
    expect(isOverMax("16", "15", true)).toBe(false);
    expect(isOverMax("", "15", false)).toBe(false);
  });

  it("previews the converted mark exactly, without floating point drift", () => {
    expect(previewConverted("12", "15", "10")).toBe("8");
    expect(previewConverted("9", "13", "10")).toBe("6.92");
    expect(previewConverted("1", "3", "1")).toBe("0.33");
    expect(previewConverted("0", "15", "10")).toBe("0");
    expect(previewConverted("12", "0", "10")).toBeNull();
  });

  it("writes a TSV template with a header and one row per student", () => {
    const text = buildTemplate(ROWS, COLUMNS, (assessmentId, studentId) =>
      assessmentId === "exam-1" && studentId === "stu-1" ? "12" : "",
    );
    const lines = text.trimEnd().split("\n");
    expect(lines[0]).toBe(
      "Student number\tStudent\tQuiz 1 (out of 15)\tQuiz 2 (out of 20)",
    );
    expect(lines[1]).toBe("STU-1\tAbel\t12\t");
  });

  it("validates an uploaded sheet and reports every issue line", () => {
    const text = [
      "Student number\tStudent\tQuiz 1 (out of 15)\tUnknown column",
      "STU-1\tAbel\t12\t5",
      "STU-1\tAbel\t13\t",
      "STU-9\tNobody\t5\t",
      "STU-2\tSara\t99\t",
      "STU-2\tSara\tbanana\t",
      "",
    ].join("\n");
    const preview = parseUpload(text, ROWS, COLUMNS, (id) => id === "exam-2");
    expect(preview.matchedStudents).toBe(1);
    expect(preview.cells).toEqual([
      {
        assessmentId: "exam-1",
        studentId: "stu-1",
        raw: "12",
        status: "present",
      },
    ]);
    expect(preview.issues.map((issue) => issue.code)).toEqual([
      "unknown_assessment",
      "duplicate",
      "unknown_student",
      "over_max",
      "invalid_value",
    ]);
    expect(preview.issues[0].line).toBe(1);
    expect(preview.issues[1].line).toBe(3);
    expect(preview.issues[2].line).toBe(4);
    expect(preview.issues[3].line).toBe(5);
  });

  it("rejects a duplicate cell and an empty upload", () => {
    const text = [
      "Student number\tStudent\tQuiz 1 (out of 15)",
      "STU-1\tAbel\t12",
      "STU-1\tAbel\t13",
    ].join("\n");
    const preview = parseUpload(text, ROWS, COLUMNS, () => false);
    expect(preview.cells).toHaveLength(1);
    expect(preview.issues[0].code).toBe("duplicate");

    expect(parseUpload("", ROWS, COLUMNS, () => false).issues[0].code).toBe(
      "invalid_value",
    );
  });

  it("splits a pasted block into trimmed cells and drops the trailing blank line", () => {
    expect(parsePasteBlock("12\t13\n14\t\n")).toEqual([
      ["12", "13"],
      ["14", ""],
    ]);
    expect(parsePasteBlock("A\nB")).toEqual([["A"], ["B"]]);
  });
});
