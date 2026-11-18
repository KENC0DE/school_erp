import { useState } from "react";
import type { ReactNode } from "react";

import { cn } from "./cn";
import { Button } from "./button";
import { EmptyState, ErrorState, SkeletonRows } from "./states";

export interface Column<Row> {
  key: string;
  header: ReactNode;
  render: (row: Row) => ReactNode;
  sortable?: boolean;
  numeric?: boolean;
  width?: string;
  hideOnPhone?: boolean;
}

export interface SortState {
  key: string;
  direction: "asc" | "desc";
}

export interface DataTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  loading?: boolean;
  error?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
  requestId?: string | null;
  requestIdLabel?: string;
  empty?: ReactNode;
  emptyTitle?: ReactNode;
  emptyDescription?: ReactNode;
  emptyAction?: ReactNode;
  toolbar?: ReactNode;
  footer?: ReactNode;
  density?: "comfortable" | "compact";
  onDensityChange?: (density: "comfortable" | "compact") => void;
  densityLabel?: string;
  sort?: SortState | null;
  onSortChange?: (sort: SortState) => void;
  caption?: string;
  className?: string;
  rowActions?: (row: Row) => ReactNode;
  /** Stack rows as cards below the phone breakpoint (default true). */
  stackOnPhone?: boolean;
}

export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  loading = false,
  error,
  onRetry,
  retryLabel = "Retry",
  requestId,
  requestIdLabel,
  empty,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  toolbar,
  footer,
  density = "comfortable",
  onDensityChange,
  densityLabel = "Density",
  sort,
  onSortChange,
  caption,
  className,
  rowActions,
  stackOnPhone = true,
}: DataTableProps<Row>) {
  const [internalDensity, setInternalDensity] = useState(density);
  const activeDensity = onDensityChange ? density : internalDensity;
  const allColumns = rowActions
    ? [...columns, { key: "__actions", header: "", render: rowActions } as Column<Row>]
    : columns;

  if (loading) {
    return (
      <div className={cn("ui-table-wrap", className)} aria-busy="true">
        <div className="ui-table__empty">
          <SkeletonRows rows={5} columns={Math.min(4, columns.length)} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("ui-table-wrap", className)}>
        <ErrorState
          title={error}
          description={onRetry ? undefined : undefined}
          requestId={requestId}
          requestIdLabel={requestIdLabel}
          retry={onRetry ? <Button onClick={onRetry}>{retryLabel}</Button> : undefined}
        />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className={cn("ui-table-wrap", className)}>
        {toolbar ? <div className="ui-table-toolbar">{toolbar}</div> : null}
        <div className="ui-table__empty">
          {empty ?? <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("ui-table-wrap", className)}>
      {toolbar || onDensityChange ? (
        <div className="ui-table-toolbar">
          <div>{toolbar}</div>
          {onDensityChange ? (
            <label className="ui-help">
              {densityLabel}
              <select
                className="ui-select"
                style={{ marginInlineStart: "var(--space-sm)", width: "auto" }}
                value={activeDensity}
                onChange={(event) => {
                  const next = event.target.value as "comfortable" | "compact";
                  setInternalDensity(next);
                  onDensityChange(next);
                }}
              >
                <option value="comfortable">comfortable</option>
                <option value="compact">compact</option>
              </select>
            </label>
          ) : null}
        </div>
      ) : null}
      <table
        className={cn(
          "ui-table",
          activeDensity === "compact" && "ui-table--compact",
          stackOnPhone && "ui-table--stack",
        )}
      >
        {caption ? <caption className="ui-visually-hidden">{caption}</caption> : null}
        <thead>
          <tr>
            {allColumns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={column.width ? { width: column.width } : undefined}
                className={cn(column.numeric && "ui-table__numeric")}
              >
                {column.sortable && onSortChange ? (
                  <button
                    type="button"
                    className="ui-table__sort"
                    onClick={() =>
                      onSortChange({
                        key: column.key,
                        direction:
                          sort?.key === column.key && sort.direction === "asc" ? "desc" : "asc",
                      })
                    }
                    aria-sort={
                      sort?.key === column.key
                        ? sort.direction === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                  >
                    {column.header}
                    <span aria-hidden="true">
                      {sort?.key === column.key ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}
                    </span>
                  </button>
                ) : (
                  column.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {allColumns.map((column) => (
                <td
                  key={column.key}
                  data-label={column.header}
                  className={cn(column.numeric && "ui-table__numeric")}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {footer ? <div className="ui-table-footer">{footer}</div> : null}
    </div>
  );
}
