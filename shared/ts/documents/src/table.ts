/**
 * Repeating-table values for the canvas preview (P5-06).
 *
 * The server renderer computes sums, averages and ranks with Python's
 * `Decimal`; the editor must show the same numbers before a document is
 * issued. This module keeps the calculation on scaled `BigInt` values, so a
 * preview never rounds through a JavaScript float.
 */

import type { TableColumn } from "./layout";

interface Scaled {
  units: bigint;
  scale: number;
}

const NUMBER = /^([+-]?)(\d+)(?:\.(\d+))?$/;

function parseDecimal(value: unknown): Scaled | null {
  if (typeof value === "boolean" || value === null || value === undefined) return null;
  let text = typeof value === "number" ? String(value) : String(value).trim();
  if (!text) return null;
  text = text.replace(/,/g, "").replace(/ETB|ብር|Br/g, "").trim();
  if (text.endsWith("%")) text = text.slice(0, -1).trim();
  const match = NUMBER.exec(text);
  if (!match) return null;
  const [, sign, whole, fraction = ""] = match;
  const units = BigInt(`${whole}${fraction}`);
  return { units: sign === "-" ? -units : units, scale: fraction.length };
}

function atScale(value: Scaled, scale: number): bigint {
  if (value.scale === scale) return value.units;
  return value.units * 10n ** BigInt(scale - value.scale);
}

function add(left: Scaled, right: Scaled): Scaled {
  const scale = Math.max(left.scale, right.scale);
  return { units: atScale(left, scale) + atScale(right, scale), scale };
}

function compare(left: Scaled, right: Scaled): number {
  const scale = Math.max(left.scale, right.scale);
  const a = atScale(left, scale);
  const b = atScale(right, scale);
  return a === b ? 0 : a < b ? -1 : 1;
}

function sum(values: Scaled[]): Scaled {
  return values.reduce((total, value) => add(total, value), { units: 0n, scale: 0 });
}

function average(values: Scaled[], places: number): Scaled {
  const total = sum(values);
  const denominator = BigInt(values.length) * 10n ** BigInt(total.scale);
  const numerator = total.units * 10n ** BigInt(places);
  let units = numerator / denominator;
  const remainder = numerator % denominator;
  if (remainder >= denominator / 2n) units += units < 0n ? -1n : 1n;
  return { units, scale: places };
}

/** Round half up, the same rule the SQL money helpers use. */
function roundTo(value: Scaled, places: number): Scaled {
  if (value.scale <= places) return { units: atScale(value, places), scale: places };
  const divisor = 10n ** BigInt(value.scale - places);
  let units = value.units / divisor;
  const remainder = value.units % divisor;
  const half = divisor / 2n;
  if (remainder >= half) units += value.units < 0n ? -1n : 1n;
  return { units, scale: places };
}

function format(value: Scaled, places?: number): string {
  const scaled = places === undefined ? value : roundTo(value, places);
  const negative = scaled.units < 0n;
  const digits = (negative ? -scaled.units : scaled.units).toString().padStart(scaled.scale + 1, "0");
  const whole = digits.slice(0, digits.length - scaled.scale) || "0";
  let fraction = scaled.scale ? digits.slice(digits.length - scaled.scale) : "";
  if (places === undefined) fraction = fraction.replace(/0+$/, "");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const text = fraction ? `${grouped}.${fraction}` : grouped;
  return negative ? `-${text}` : text;
}

function getPath(row: Record<string, unknown>, path: string): unknown {
  let current: unknown = row;
  for (const part of path.split(".")) {
    if (current === null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function cell(row: Record<string, unknown>, column: TableColumn): unknown {
  if (column.binding === undefined) return "";
  return getPath(row, column.binding);
}

/**
 * Resolve every column for every row. Base columns keep their raw value;
 * computed columns produce a display string.
 */
export function computeTableValues(
  rows: Record<string, unknown>[],
  columns: TableColumn[],
): Record<string, string>[] {
  const values: Record<string, unknown>[] = rows.map((row) => {
    const current: Record<string, unknown> = {};
    for (const column of columns) {
      current[column.key] = column.binding === undefined ? "" : cell(row, column);
    }
    return current;
  });

  for (const column of columns) {
    const computed = column.computed;
    if (computed === undefined || computed.op === "rank") continue;
    for (const current of values) {
      const numbers = computed.of
        .map((reference) => parseDecimal(current[reference]))
        .filter((number): number is Scaled => number !== null);
      if (numbers.length === 0) {
        current[column.key] = undefined;
        continue;
      }
      if (computed.op === "sum") {
        current[column.key] = format(
          sum(numbers),
          column.format?.number_decimals,
        );
      } else {
        const places = column.format?.number_decimals ?? 2;
        current[column.key] = format(
          average(numbers, places),
          column.format?.number_decimals,
        );
      }
    }
  }

  for (const column of columns) {
    const computed = column.computed;
    if (computed === undefined || computed.op !== "rank") continue;
    const ranked = values
      .map((current, index) => ({ index, number: parseDecimal(current[computed.by]) }))
      .filter((entry): entry is { index: number; number: Scaled } => entry.number !== null)
      .sort((left, right) => {
        const order = compare(left.number, right.number);
        return computed.descending ? -order : order;
      });
    let previous: Scaled | null = null;
    let rank = 0;
    ranked.forEach((entry, position) => {
      if (previous === null || compare(previous, entry.number) !== 0) {
        rank = position + 1;
        previous = entry.number;
      }
      values[entry.index][column.key] = String(rank);
    });
    for (const current of values) {
      if (!(column.key in current)) current[column.key] = undefined;
    }
  }

  return values.map((current) =>
    Object.fromEntries(
      columns.map((column) => {
        const value = current[column.key];
        if (column.computed !== undefined) {
          return [column.key, value === undefined ? "" : String(value)];
        }
        return [column.key, value === undefined || value === null ? "" : String(value)];
      }),
    ),
  );
}

/** Totals, averages and counts for a table footer, in scaled decimals. */
export function summarizeColumn(
  values: Record<string, string>[],
  key: string,
  aggregate: "sum" | "average" | "count",
  decimals?: number,
): string {
  if (aggregate === "count") {
    return String(values.filter((row) => row[key] !== "").length);
  }
  const numbers = values
    .map((row) => parseDecimal(row[key]))
    .filter((value): value is Scaled => value !== null);
  if (numbers.length === 0) return "0";
  if (aggregate === "average") {
    const places = decimals ?? 2;
    return format(average(numbers, places), decimals);
  }
  return format(sum(numbers), decimals);
}
