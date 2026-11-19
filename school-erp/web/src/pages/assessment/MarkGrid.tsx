import { useMemo, useRef } from "react";

import { useI18n } from "../../providers/I18nProvider";
import {
  cellKey,
  isOverMax,
  parseCellToken,
  parsePasteBlock,
  previewConverted,
  statusFromKey,
  type CellValue,
  type MarkColumn,
  type MarkRow,
} from "./marks";
import { fromMicro, toMicro, type ScoreStatus } from "./types";

export interface MarkCell {
  raw: string;
  status: ScoreStatus;
  version: number | null;
  scoreId: string | null;
  converted: string | null;
  savedRaw: string;
  savedStatus: ScoreStatus;
  pending: boolean;
  saving: boolean;
  error: string | null;
  conflict: boolean;
}

interface MarkGridProps {
  rows: MarkRow[];
  columns: MarkColumn[];
  cells: Record<string, MarkCell>;
  readOnly: boolean;
  precision: number;
  onChange: (assessmentId: string, studentId: string, value: CellValue) => void;
  onSaveNow: (assessmentId: string, studentId: string) => void;
  onRevert: (assessmentId: string, studentId: string) => void;
  onPasteIssues: (count: number) => void;
  onFocusCell: (assessmentId: string, studentId: string) => void;
}

function cellId(rowIndex: number, columnIndex: number): string {
  return `mark-cell-${rowIndex}-${columnIndex}`;
}

function statusLabel(t: (key: string) => string, status: ScoreStatus): string {
  return t(`assessment.marks.status.${status}`);
}

export function MarkGrid({
  rows,
  columns,
  cells,
  readOnly,
  precision,
  onChange,
  onSaveNow,
  onRevert,
  onPasteIssues,
  onFocusCell,
}: MarkGridProps) {
  const { t } = useI18n();
  const inputs = useRef(new Map<string, HTMLInputElement>());

  const move = (
    rowIndex: number,
    columnIndex: number,
    rowDelta: number,
    columnDelta: number,
  ) => {
    const nextRow = Math.min(rows.length - 1, Math.max(0, rowIndex + rowDelta));
    const nextColumn = Math.min(
      columns.length - 1,
      Math.max(0, columnIndex + columnDelta),
    );
    inputs.current.get(cellId(nextRow, nextColumn))?.focus();
  };

  const apply = (
    assessmentId: string,
    studentId: string,
    token: string,
  ): boolean => {
    const parsed = parseCellToken(token);
    if (parsed === null) return false;
    onChange(assessmentId, studentId, parsed);
    return true;
  };

  const handlePaste = (
    event: React.ClipboardEvent<HTMLInputElement>,
    rowIndex: number,
    columnIndex: number,
  ) => {
    const text = event.clipboardData?.getData("text/plain") ?? "";
    if (!text.includes("\t") && !text.includes("\n")) return;
    event.preventDefault();
    const block = parsePasteBlock(text);
    let issues = 0;
    block.forEach((line, rowOffset) => {
      line.forEach((token, columnOffset) => {
        const row = rows[rowIndex + rowOffset];
        const column = columns[columnIndex + columnOffset];
        if (row === undefined || column === undefined) {
          issues += 1;
          return;
        }
        if (token === "") return;
        if (!apply(column.id, row.studentId, token)) issues += 1;
      });
    });
    onPasteIssues(issues);
  };

  const footer = useMemo(() => {
    return columns.map((column) => {
      let total = 0n;
      let count = 0;
      let highest: bigint | null = null;
      let lowest: bigint | null = null;
      let entered = 0;
      for (const row of rows) {
        const cell = cells[cellKey(column.id, row.studentId)];
        if (cell === undefined) continue;
        if (cell.status !== "present" || cell.raw.trim() !== "") entered += 1;
        const value = cell.raw.trim()
          ? previewConverted(
              cell.raw,
              column.outOf,
              column.componentMax,
              precision,
            )
          : null;
        if (value === null) continue;
        const parsed = toMicro(value);
        if (parsed === null) continue;
        total += parsed;
        count += 1;
        highest = highest === null || parsed > highest ? parsed : highest;
        lowest = lowest === null || parsed < lowest ? parsed : lowest;
      }
      const average = count === 0 ? null : fromMicro(total / BigInt(count));
      return {
        id: column.id,
        entered,
        average,
        highest: highest === null ? "—" : fromMicro(highest),
        lowest: lowest === null ? "—" : fromMicro(lowest),
      };
    });
  }, [cells, columns, precision, rows]);

  const flagged = rows.reduce((count, row) => {
    return (
      count +
      columns.filter((column) => {
        const cell = cells[cellKey(column.id, row.studentId)];
        if (cell === undefined) return false;
        return isOverMax(cell.raw, column.outOf, column.allowBonus);
      }).length
    );
  }, 0);

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-md border border-border">
        <table
          className="w-full border-collapse text-sm"
          data-testid="mark-grid"
        >
          <thead>
            <tr className="bg-muted/60 text-left">
              <th className="sticky left-0 z-10 min-w-48 bg-muted/60 px-3 py-2 font-medium">
                {t("assessment.marks.student")}
              </th>
              {columns.map((column) => (
                <th
                  key={column.id}
                  className="min-w-24 px-2 py-2 font-medium"
                  scope="col"
                >
                  <span className="block">{column.title}</span>
                  <span className="block text-xs font-normal text-muted-foreground">
                    {t("assessment.marks.out_of")} {column.outOf}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={row.studentId} className="border-t border-border">
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-background px-3 py-1.5 text-left font-normal"
                >
                  <span className="block font-medium">{row.studentName}</span>
                  <span className="block text-xs text-muted-foreground">
                    {row.rollNumber ? `${row.rollNumber} · ` : ""}
                    {row.studentNumber}
                  </span>
                </th>
                {columns.map((column, columnIndex) => {
                  const cell = cells[cellKey(column.id, row.studentId)];
                  const over = cell
                    ? isOverMax(cell.raw, column.outOf, column.allowBonus)
                    : false;
                  const preview =
                    cell && cell.status === "present" && cell.raw.trim()
                      ? previewConverted(
                          cell.raw,
                          column.outOf,
                          column.componentMax,
                          precision,
                        )
                      : cell?.status === "present"
                        ? cell.converted
                        : null;
                  return (
                    <td key={column.id} className="px-1 py-1 align-top">
                      <input
                        id={cellId(rowIndex, columnIndex)}
                        data-testid={cellId(rowIndex, columnIndex)}
                        data-row={rowIndex}
                        data-col={columnIndex}
                        ref={(node) => {
                          if (node)
                            inputs.current.set(
                              cellId(rowIndex, columnIndex),
                              node,
                            );
                          else
                            inputs.current.delete(
                              cellId(rowIndex, columnIndex),
                            );
                        }}
                        className={`w-20 rounded border px-2 py-1 text-right tabular-nums ${
                          over ? "border-destructive" : "border-input"
                        }`}
                        aria-label={t("assessment.marks.cell_label", {
                          student: row.studentName,
                          assessment: column.title,
                        })}
                        aria-invalid={over || Boolean(cell?.conflict)}
                        inputMode="decimal"
                        value={cell?.raw ?? ""}
                        data-status={cell?.status ?? "present"}
                        disabled={readOnly}
                        onFocus={() => onFocusCell(column.id, row.studentId)}
                        onChange={(event) => {
                          const value = event.target.value;
                          if (!/^\d*(?:\.\d{0,6})?$/.test(value)) return;
                          onChange(column.id, row.studentId, {
                            raw: value,
                            status: "present",
                          });
                        }}
                        onBlur={() => onSaveNow(column.id, row.studentId)}
                        onPaste={(event) =>
                          handlePaste(event, rowIndex, columnIndex)
                        }
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            onSaveNow(column.id, row.studentId);
                            move(rowIndex, columnIndex, 1, 0);
                            return;
                          }
                          if (event.key === "ArrowDown") {
                            event.preventDefault();
                            move(rowIndex, columnIndex, 1, 0);
                            return;
                          }
                          if (event.key === "ArrowUp") {
                            event.preventDefault();
                            move(rowIndex, columnIndex, -1, 0);
                            return;
                          }
                          if (
                            event.key === "ArrowLeft" &&
                            event.currentTarget.selectionStart === 0
                          ) {
                            event.preventDefault();
                            move(rowIndex, columnIndex, 0, -1);
                            return;
                          }
                          if (
                            event.key === "ArrowRight" &&
                            event.currentTarget.selectionStart ===
                              event.currentTarget.value.length
                          ) {
                            event.preventDefault();
                            move(rowIndex, columnIndex, 0, 1);
                            return;
                          }
                          if (event.key === "Escape") {
                            event.preventDefault();
                            onRevert(column.id, row.studentId);
                            return;
                          }
                          const status = statusFromKey(event.key);
                          if (status !== null) {
                            event.preventDefault();
                            onChange(column.id, row.studentId, {
                              raw: "",
                              status,
                            });
                            onSaveNow(column.id, row.studentId);
                          }
                        }}
                      />
                      <div className="mt-0.5 flex items-center justify-between gap-1 px-1 text-xs text-muted-foreground">
                        <span
                          data-testid={`mark-converted-${rowIndex}-${columnIndex}`}
                        >
                          {cell?.status !== "present"
                            ? statusLabel(t, cell?.status ?? "present")
                            : (preview ?? "—")}
                        </span>
                        {cell?.saving ? (
                          <span
                            data-testid={`mark-saving-${rowIndex}-${columnIndex}`}
                          >
                            {t("assessment.marks.saving")}
                          </span>
                        ) : cell?.error ? (
                          <span
                            className="text-destructive"
                            title={cell.error}
                            data-testid={`mark-error-${rowIndex}-${columnIndex}`}
                          >
                            {cell.conflict ? "!" : "×"}
                          </span>
                        ) : cell?.pending ? (
                          <span
                            data-testid={`mark-pending-${rowIndex}-${columnIndex}`}
                          >
                            •
                          </span>
                        ) : cell?.status === "present" && cell.raw ? (
                          <span aria-hidden="true">✓</span>
                        ) : null}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-border bg-muted/40 text-xs">
              <th className="sticky left-0 z-10 bg-muted/40 px-3 py-1.5 text-left font-medium">
                {t("assessment.marks.footer")}
              </th>
              {footer.map((column) => (
                <td
                  key={column.id}
                  className="px-2 py-1.5"
                  data-testid={`mark-stats-${column.id}`}
                >
                  <span className="block">
                    {t("assessment.marks.entered_count", {
                      entered: column.entered,
                      total: rows.length,
                    })}
                  </span>
                  <span className="block tabular-nums text-muted-foreground">
                    {t("assessment.marks.stat_line", {
                      average: column.average ?? "—",
                      highest: column.highest,
                      lowest: column.lowest,
                    })}
                  </span>
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="text-xs text-muted-foreground" data-testid="mark-flagged">
        {t("assessment.marks.flagged", { count: flagged })}
      </p>
    </div>
  );
}
