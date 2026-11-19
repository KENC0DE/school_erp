import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { cn } from "./cn";

export type ToastVariant = "success" | "danger" | "info";

export interface ToastInput {
  title: ReactNode;
  description?: ReactNode;
  variant?: ToastVariant;
  duration?: number;
}

interface ToastItem extends ToastInput {
  id: number;
}

interface ToastApi {
  push: (toast: ToastInput) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const push = useCallback((toast: ToastInput) => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { ...toast, id }]);
  }, []);

  const api = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="ui-toast-region" aria-live="polite" aria-relevant="additions">
        {items.map((item) => (
          <Toast key={item.id} item={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function Toast({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(item.id), item.duration ?? 4500);
    return () => window.clearTimeout(timer);
  }, [item, onDismiss]);

  return (
    <div
      className={cn("ui-toast", item.variant && `ui-toast--${item.variant}`)}
      role={item.variant === "danger" ? "alert" : "status"}
    >
      <div>
        <strong>{item.title}</strong>
        {item.description ? <div className="ui-help">{item.description}</div> : null}
      </div>
      <button
        type="button"
        className="ui-btn ui-btn--ghost ui-btn--sm ui-btn--icon"
        aria-label="Dismiss"
        onClick={() => onDismiss(item.id)}
      >
        ×
      </button>
    </div>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
