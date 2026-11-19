import {
  displayConverted,
  isChanged,
  isOverMax,
  nextRowIndex,
  parseMarkInput,
  previewConverted,
  requestValue,
  statusFromKey,
} from "../src/assessment/marks";
import type { ScoreItem } from "../src/assessment/types";

function item(overrides: Partial<ScoreItem> = {}): ScoreItem {
  return {
    score_id: null,
    student_id: "student-1",
    student_number: "STU-0001",
    student_name: "Abebe Bekele",
    student_name_am: null,
    roll_number: "1",
    enrolled: true,
    raw_score: null,
    out_of: "100",
    status: "present",
    converted: null,
    note: null,
    row_version: null,
    entered_at: null,
    ...overrides,
  };
}

describe("mobile mark helpers", () => {
  it("parses a decimal keypad entry and rejects anything else", () => {
    expect(parseMarkInput(" 87.5 ")).toEqual({
      raw: "87.5",
      status: "present",
    });
    expect(parseMarkInput("")).toEqual({ raw: "", status: "present" });
    expect(parseMarkInput("8a")).toBeNull();
    expect(parseMarkInput("1.2345678")).toBeNull();
  });

  it("maps status shortcuts without stealing numeric input", () => {
    expect(statusFromKey("a")).toBe("absent");
    expect(statusFromKey("E")).toBe("excused");
    expect(statusFromKey("x")).toBe("exempt");
    expect(statusFromKey("\u2013")).toBe("not_taken");
    expect(statusFromKey("7")).toBeNull();
  });

  it("previews the converted mark with the backend rounding", () => {
    expect(previewConverted("8", "10", "20")).toBe("16");
    expect(previewConverted("1", "3", "10", 2)).toBe("3.33");
    expect(previewConverted("100", "100", "40")).toBe("40");
    expect(previewConverted("", "100", "40")).toBeNull();
    expect(displayConverted({ raw: "9", status: "present" }, "10", "20")).toBe(
      "18",
    );
    expect(
      displayConverted({ raw: "", status: "absent" }, "10", "20"),
    ).toBeNull();
  });

  it("flags a mark above the maximum unless bonus marks are allowed", () => {
    expect(isOverMax("11", "10", false)).toBe(true);
    expect(isOverMax("11", "10", true)).toBe(false);
    expect(isOverMax("", "10", false)).toBe(false);
  });

  it("moves auto-advance to the next row and clamps at the end", () => {
    expect(nextRowIndex(3, 0)).toBe(1);
    expect(nextRowIndex(3, 2)).toBe(2);
    expect(nextRowIndex(0, 4)).toBe(0);
  });

  it("only treats a real change as dirty", () => {
    expect(
      isChanged({ raw: "7", status: "present" }, item({ raw_score: "7" })),
    ).toBe(false);
    expect(
      isChanged({ raw: "8", status: "present" }, item({ raw_score: "7" })),
    ).toBe(true);
    expect(
      isChanged({ raw: "", status: "absent" }, item({ status: "present" })),
    ).toBe(true);
    expect(isChanged({ raw: "", status: "present" }, undefined)).toBe(false);
  });

  it("sends no raw mark for a non-numeric status", () => {
    expect(requestValue({ raw: "9", status: "present" })).toEqual({
      raw_score: "9",
      status: "present",
    });
    expect(requestValue({ raw: "9", status: "absent" })).toEqual({
      raw_score: null,
      status: "absent",
    });
    expect(requestValue({ raw: "", status: "present" })).toEqual({
      raw_score: null,
      status: "present",
    });
  });
});
