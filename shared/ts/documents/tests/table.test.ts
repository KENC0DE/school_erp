import { describe, expect, it } from "vitest";

import type { TableColumn } from "../src/layout";
import { computeTableValues, summarizeColumn } from "../src/table";

const columns: TableColumn[] = [
  { key: "subject", label: "Subject", binding: "subject", align: "left" },
  { key: "classwork", label: "Class work", binding: "classwork", align: "right" },
  { key: "test", label: "Test", binding: "test", align: "right" },
  { key: "final", label: "Final", binding: "final", align: "right" },
  {
    key: "total",
    label: "Total",
    computed: { op: "sum", of: ["classwork", "test", "final"] },
    align: "right",
    format: { number_decimals: 2 },
  },
  {
    key: "average",
    label: "Average",
    computed: { op: "average", of: ["classwork", "test", "final"] },
    align: "right",
    format: { number_decimals: 2 },
  },
  {
    key: "rank",
    label: "Rank",
    computed: { op: "rank", by: "total", descending: true },
    align: "center",
  },
];

describe("repeating table values", () => {
  it("adds and averages components without a float round trip", () => {
    const values = computeTableValues(
      [{ subject: "Maths", classwork: "8.5", test: "15", final: "60.25" }],
      columns,
    );
    expect(values[0].total).toBe("83.75");
    expect(values[0].average).toBe("27.92");
  });

  it("ignores blank components in an average", () => {
    const values = computeTableValues(
      [{ subject: "Maths", classwork: "10", test: "", final: "20" }],
      columns,
    );
    expect(values[0].total).toBe("30.00");
    expect(values[0].average).toBe("15.00");
  });

  it("ranks rows with competition ranking and ties", () => {
    const values = computeTableValues(
      [
        { subject: "Maths", classwork: "10", test: "20", final: "30" },
        { subject: "English", classwork: "5", test: "10", final: "15" },
        { subject: "Science", classwork: "10", test: "20", final: "30" },
      ],
      columns,
    );
    expect(values.map((row) => row.total)).toEqual(["60.00", "30.00", "60.00"]);
    // First and third tie for first; the middle row is third, not second.
    expect(values.map((row) => row.rank)).toEqual(["1", "3", "1"]);
  });

  it("supports ascending rank and summary rows", () => {
    const ascending: TableColumn[] = columns.map((column) =>
      column.computed?.op === "rank"
        ? { ...column, computed: { ...column.computed, descending: false } }
        : column,
    );
    const values = computeTableValues(
      [
        { subject: "Maths", classwork: "10", test: "20", final: "30" },
        { subject: "English", classwork: "5", test: "10", final: "15" },
      ],
      ascending,
    );
    expect(values.map((row) => row.rank)).toEqual(["2", "1"]);
    expect(summarizeColumn(values, "total", "sum")).toBe("90");
    expect(summarizeColumn(values, "total", "average", 2)).toBe("45.00");
    expect(summarizeColumn(values, "subject", "count")).toBe("2");
  });
});
