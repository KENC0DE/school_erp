import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { roleMessageKey, useT } from "../i18n";
import { cn } from "../lib/utils";
import { useAuth } from "../providers/AuthProvider";
import { useTheme } from "../providers/ThemeProvider";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";

const NAV_ITEMS = [
  { to: "/schools", key: "controller.nav.schools", testId: "nav-schools" },
  { to: "/vault", key: "controller.nav.vault", testId: "nav-vault" },
] as const;

export function Shell() {
  const t = useT();
  const { user, logout } = useAuth();
  const { mode, toggle } = useTheme();
  const navigate = useNavigate();

  const onLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="flex w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
        <div className="border-b border-sidebar-border px-5 py-5">
          <div className="text-base font-semibold">{t("controller.app.brand")}</div>
          <div className="text-xs text-muted-foreground">{t("controller.app.brandSuffix")}</div>
        </div>
        <nav aria-label={t("controller.nav.label")} className="flex flex-col gap-1 p-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              data-testid={item.testId}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "hover:bg-sidebar-accent/60",
                )
              }
            >
              {t(item.key)}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-border bg-card px-6 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold" data-testid="current-user">
              {user?.display_name}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{user?.email}</span>
              {user ? <Badge data-testid="current-role">{t(roleMessageKey(user.role))}</Badge> : null}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={toggle}
              aria-label={t(
                mode === "light"
                  ? "controller.header.themeToDark"
                  : "controller.header.themeToLight",
              )}
              data-testid="theme-toggle"
            >
              {t(
                mode === "light"
                  ? "controller.header.themeToDark"
                  : "controller.header.themeToLight",
              )}
            </Button>
            <Button variant="secondary" onClick={onLogout} data-testid="logout">
              {t("controller.header.logout")}
            </Button>
          </div>
        </header>
        <main className="min-w-0 flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
