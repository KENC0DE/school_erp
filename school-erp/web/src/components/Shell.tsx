import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";

import { api, type Navigation } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";
import { useTheme } from "../providers/ThemeProvider";
import { ChatPanel } from "./ChatPanel";
import { Button } from "./ui/Button";

const LANGUAGE_LABELS: Record<string, string> = { en: "English", am: "አማርኛ" };

export function Shell() {
  const { t, locale, languages, setLocale } = useI18n();
  const { mode, toggle } = useTheme();
  const { user, logout } = useAuth();

  const nav = useQuery({
    queryKey: ["navigation"],
    queryFn: () => api.get<Navigation>("/api/v1/auth/me/navigation"),
  });

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex">
        <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-primary text-sm font-bold text-sidebar-primary-foreground">
            SE
          </span>
          <span className="font-semibold">{t("app.name")}</span>
        </div>
        <nav aria-label={t("nav.dashboard")} className="flex-1 space-y-1 p-3">
          {(nav.data?.items ?? []).map((item) => (
            <NavLink
              key={item.key}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                }`
              }
            >
              {t(item.label_key)}
            </NavLink>
          ))}
        </nav>
        {nav.isError ? <p className="px-5 pb-4 text-xs text-destructive">{t("common.error")}</p> : null}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between gap-4 border-b border-border bg-card px-4 md:px-6">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{user?.display_name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {user?.is_controller ? t("controller.session_opened") : user?.email}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="sr-only" htmlFor="locale-switch">
              {t("common.language")}
            </label>
            <select
              id="locale-switch"
              value={locale}
              onChange={(event) => setLocale(event.target.value)}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            >
              {languages.map((code) => (
                <option key={code} value={code}>
                  {LANGUAGE_LABELS[code] ?? code}
                </option>
              ))}
            </select>
            <Button variant="outline" onClick={toggle} aria-label={t("common.theme")}>
              {mode === "dark" ? t("common.theme.light") : t("common.theme.dark")}
            </Button>
            <Button variant="ghost" onClick={() => void logout()}>
              {t("auth.logout")}
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
      <ChatPanel />
    </div>
  );
}
