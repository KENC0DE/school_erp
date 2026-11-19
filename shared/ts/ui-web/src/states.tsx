import type { CSSProperties, ReactNode } from "react";

import { cn } from "./cn";

export interface SkeletonProps {
  variant?: "text" | "rect" | "circle";
  width?: CSSProperties["width"];
  height?: CSSProperties["height"];
  className?: string;
}

export function Skeleton({ variant = "rect", width, height, className }: SkeletonProps) {
  return (
    <span
      aria-hidden="true"
      className={cn("ui-skeleton", variant === "text" && "ui-skeleton--text", variant === "circle" && "ui-skeleton--circle", className)}
      style={{ width, height }}
    />
  );
}

export function SkeletonRows({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="ui-field" aria-hidden="true">
      {Array.from({ length: rows }).map((_, row) => (
        <div key={row} style={{ display: "grid", gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`, gap: "var(--space-base)" }}>
          {Array.from({ length: columns }).map((__, column) => (
            <Skeleton key={column} variant="text" />
          ))}
        </div>
      ))}
    </div>
  );
}

export interface LoadingStateProps {
  /** Announced to assistive technology; the skeleton itself is decorative. */
  label?: ReactNode;
  rows?: number;
  columns?: number;
  className?: string;
  testId?: string;
}

export function LoadingState({ label, rows = 4, columns = 3, className, testId }: LoadingStateProps) {
  return (
    <div
      className={cn("ui-state", "ui-state--loading", className)}
      data-testid={testId}
      data-ui-state="loading"
      role="status"
      aria-busy="true"
    >
      {label ? <span className="ui-visually-hidden">{label}</span> : null}
      <SkeletonRows rows={rows} columns={columns} />
    </div>
  );
}

export interface EmptyStateProps {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
  testId?: string;
}

export function EmptyState({ icon, title, description, action, className, testId }: EmptyStateProps) {
  return (
    <div
      className={cn("ui-state", className)}
      role="status"
      data-testid={testId}
      data-ui-state="empty"
    >
      {icon ? <span className="ui-state__icon">{icon}</span> : null}
      <p className="ui-state__title">{title}</p>
      {description ? <p className="ui-state__description">{description}</p> : null}
      {action}
    </div>
  );
}

export interface ErrorStateProps {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  requestId?: string | null;
  requestIdLabel?: string;
  retry?: ReactNode;
  className?: string;
  testId?: string;
}

export function ErrorState({
  icon,
  title,
  description,
  requestId,
  requestIdLabel,
  retry,
  className,
  testId,
}: ErrorStateProps) {
  return (
    <div
      className={cn("ui-state", className)}
      role="alert"
      data-testid={testId}
      data-ui-state="error"
    >
      {icon ? <span className="ui-state__icon">{icon}</span> : null}
      <p className="ui-state__title">{title}</p>
      {description ? <p className="ui-state__description">{description}</p> : null}
      {requestId ? (
        <p className="ui-state__request-id">
          {requestIdLabel ?? "Request id"}: <span className="ui-num">{requestId}</span>
        </p>
      ) : null}
      {retry}
    </div>
  );
}

export interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  breadcrumbs?: ReactNode;
  actions?: ReactNode;
  /** Heading level; keep one h1 per page and use 2 for nested sections. */
  level?: 1 | 2 | 3;
  className?: string;
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  level = 1,
  className,
}: PageHeaderProps) {
  const Heading = `h${level}` as "h1" | "h2" | "h3";
  return (
    <header className={cn("ui-page-header", className)}>
      <div>
        {breadcrumbs}
        <Heading className="ui-page-header__title">{title}</Heading>
        {description ? <p className="ui-page-header__description">{description}</p> : null}
      </div>
      {actions ? <div className="ui-page-header__actions">{actions}</div> : null}
    </header>
  );
}

export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("ui-page", className)}>{children}</div>;
}
