import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

export type ButtonVariant = "primary" | "default" | "secondary" | "outline" | "ghost" | "destructive";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  iconOnly?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  loading = false,
  iconOnly = false,
  leftIcon,
  rightIcon,
  children,
  disabled,
  type = "button",
  ...props
}: ButtonProps) {
  const resolved = variant === "default" ? "primary" : variant;
  return (
    <button
      type={type}
      className={cn(
        "ui-btn",
        `ui-btn--${resolved}`,
        size === "sm" && "ui-btn--sm",
        size === "lg" && "ui-btn--lg",
        iconOnly && "ui-btn--icon",
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <span className="ui-btn__spinner" aria-hidden="true" /> : leftIcon}
      {children}
      {rightIcon}
    </button>
  );
}
