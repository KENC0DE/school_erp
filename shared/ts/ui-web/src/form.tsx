import type { FormEvent, ReactNode } from "react";

import { cn } from "./cn";

export interface FormLayoutProps {
  children: ReactNode;
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
  className?: string;
  noValidate?: boolean;
}

export function FormLayout({ children, onSubmit, className, noValidate }: FormLayoutProps) {
  return (
    <form className={cn("ui-form", className)} onSubmit={onSubmit} noValidate={noValidate}>
      {children}
    </form>
  );
}

export function FormSection({
  title,
  description,
  children,
  className,
}: {
  title?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("ui-form__section", className)}>
      {title ? <h2 className="ui-form__section-title">{title}</h2> : null}
      {description ? <p className="ui-help">{description}</p> : null}
      {children}
    </section>
  );
}

export function FormGrid({ children, single }: { children: ReactNode; single?: boolean }) {
  return <div className={cn("ui-form__grid", single && "ui-form__grid--single")}>{children}</div>;
}

export function FormSpan({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("ui-form__span-2", className)}>{children}</div>;
}

export function SaveBar({ children }: { children: ReactNode }) {
  return <div className="ui-savebar">{children}</div>;
}
