import { useId, useState } from "react";
import type { ReactNode } from "react";

import { cn } from "./cn";

export interface TabItem {
  key: string;
  label: ReactNode;
  content: ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  items: TabItem[];
  initialKey?: string;
  value?: string;
  onChange?: (key: string) => void;
  className?: string;
}

export function Tabs({ items, initialKey, value, onChange, className }: TabsProps) {
  const baseId = useId();
  const [internal, setInternal] = useState(initialKey ?? items[0]?.key);
  const active = value ?? internal;
  const selected = items.find((item) => item.key === active) ?? items[0];

  return (
    <div className={cn("ui-tabs", className)}>
      <div className="ui-tablist" role="tablist">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            className="ui-tab"
            role="tab"
            id={`${baseId}-tab-${item.key}`}
            aria-selected={item.key === selected?.key}
            aria-controls={`${baseId}-panel-${item.key}`}
            disabled={item.disabled}
            tabIndex={item.key === selected?.key ? 0 : -1}
            onClick={() => {
              setInternal(item.key);
              onChange?.(item.key);
            }}
            onKeyDown={(event) => {
              if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
              const index = items.findIndex((entry) => entry.key === selected?.key);
              const next = event.key === "ArrowRight" ? index + 1 : index - 1;
              const target = items[(next + items.length) % items.length];
              setInternal(target.key);
              onChange?.(target.key);
              document.getElementById(`${baseId}-tab-${target.key}`)?.focus();
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      {selected ? (
        <div
          role="tabpanel"
          id={`${baseId}-panel-${selected.key}`}
          aria-labelledby={`${baseId}-tab-${selected.key}`}
        >
          {selected.content}
        </div>
      ) : null}
    </div>
  );
}
