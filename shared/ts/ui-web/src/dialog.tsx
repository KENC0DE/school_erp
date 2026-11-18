import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

import { Button } from "./button";
import { cn } from "./cn";

interface OverlayProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  closeLabel?: string;
}

function useOverlay(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const focusable = node?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const items = Array.from(
        node.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((item) => item.offsetParent !== null);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [open, onClose]);

  return ref;
}

function Header({
  title,
  description,
  titleId,
  onClose,
  closeLabel,
}: {
  title: ReactNode;
  description?: ReactNode;
  titleId: string;
  onClose: () => void;
  closeLabel: string;
}) {
  return (
    <div className="ui-dialog__header">
      <div>
        <h2 className="ui-dialog__title" id={titleId}>
          {title}
        </h2>
        {description ? <p className="ui-dialog__description">{description}</p> : null}
      </div>
      <Button variant="ghost" size="sm" iconOnly onClick={onClose} aria-label={closeLabel}>
        ×
      </Button>
    </div>
  );
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  wide,
  closeLabel = "Close",
}: OverlayProps) {
  const titleId = useId();
  const ref = useOverlay(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="ui-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div
        ref={ref}
        className={cn("ui-dialog", wide && "ui-dialog--wide")}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <Header title={title} description={description} titleId={titleId} onClose={onClose} closeLabel={closeLabel} />
        <div className="ui-dialog__body">{children}</div>
        {footer ? <div className="ui-dialog__footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}

export function SideSheet({ open, onClose, title, description, children, footer, closeLabel = "Close" }: OverlayProps) {
  const titleId = useId();
  const ref = useOverlay(open, onClose);
  if (!open) return null;
  return createPortal(
    <>
      <div className="ui-backdrop" onMouseDown={onClose} aria-hidden="true" />
      <aside ref={ref} className="ui-sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <Header title={title} description={description} titleId={titleId} onClose={onClose} closeLabel={closeLabel} />
        <div className="ui-sheet__body">{children}</div>
        {footer ? <div className="ui-dialog__footer">{footer}</div> : null}
      </aside>
    </>,
    document.body,
  );
}
