import { PanelLeftClose, PanelLeftOpen, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "./button";
import { cn } from "./cn";

export interface ShellNavItem {
  key: string;
  label: ReactNode;
  href?: string;
  icon?: ReactNode;
  active?: boolean;
}

export interface SidebarProps {
  brand: ReactNode;
  items: ShellNavItem[];
  renderLink?: (item: ShellNavItem, className: string) => ReactNode;
  footer?: ReactNode;
  navLabel: string;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  className?: string;
}

export function Sidebar({
  brand,
  items,
  renderLink,
  footer,
  navLabel,
  collapsed = false,
  onToggleCollapsed,
  className,
}: SidebarProps) {
  return (
    <aside className={cn("ui-sidebar", collapsed && "ui-sidebar--rail", className)}>
      <div className="ui-sidebar__brand">
        {brand}
        {onToggleCollapsed ? (
          <Button
            variant="ghost"
            size="sm"
            iconOnly
            className="ml-auto"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </Button>
        ) : null}
      </div>
      <nav className="ui-sidebar__nav" aria-label={navLabel}>
        {items.map((item) =>
          renderLink ? (
            <div key={item.key}>{renderLink(item, cn("ui-navlink", item.active && "ui-navlink--active"))}</div>
          ) : (
            <a
              key={item.key}
              href={item.href ?? "#"}
              className={cn("ui-navlink", item.active && "ui-navlink--active")}
              aria-current={item.active ? "page" : undefined}
            >
              {item.icon}
              {collapsed ? <span className="ui-visually-hidden">{item.label}</span> : item.label}
            </a>
          ),
        )}
      </nav>
      {footer ? <div className="ui-sidebar__nav">{footer}</div> : null}
    </aside>
  );
}

export interface TopBarProps {
  identity?: ReactNode;
  muted?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function TopBar({ identity, muted, actions, className }: TopBarProps) {
  return (
    <header className={cn("ui-topbar", className)}>
      <div className="ui-topbar__identity">
        {identity ? <div>{identity}</div> : null}
        {muted ? <div className="ui-topbar__muted">{muted}</div> : null}
      </div>
      {actions ? <div className="ui-topbar__actions">{actions}</div> : null}
    </header>
  );
}

export function AppShell({
  sidebar,
  banner,
  topbar,
  children,
  className,
}: {
  sidebar: ReactNode;
  banner?: ReactNode;
  topbar: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("ui-shell", className)}>
      {sidebar}
      <div className="ui-main">
        {banner}
        {topbar}
        <main className="ui-content">{children}</main>
      </div>
    </div>
  );
}

export interface ControllerSessionBannerProps {
  message: ReactNode;
  reason?: ReactNode;
  readOnly?: boolean;
  readOnlyMessage?: ReactNode;
  className?: string;
}

export function ControllerSessionBanner({
  message,
  reason,
  readOnly,
  readOnlyMessage,
  className,
}: ControllerSessionBannerProps) {
  return (
    <div
      className={cn("ui-banner", readOnly && "ui-banner--read-only", className)}
      role="status"
      data-testid="controller-session-banner"
    >
      <span className="ui-banner__icon" aria-hidden="true">
        <ShieldAlert size={18} />
      </span>
      <span>{message}</span>
      {reason ? <span className="ui-topbar__muted">{reason}</span> : null}
      {readOnly && readOnlyMessage ? <span>{readOnlyMessage}</span> : null}
    </div>
  );
}
