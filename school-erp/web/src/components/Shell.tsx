import { useQuery } from "@tanstack/react-query";
import {
  AppShell,
  Button,
  ControllerSessionBanner,
  Sidebar,
  Skeleton,
  TopBar,
} from "@erp/ui-web";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { api, type Navigation } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";
import { useTheme } from "../providers/ThemeProvider";
import { ChatPanel } from "./ChatPanel";
import { ThemePicker } from "./ThemePicker";

export function Shell() {
  const { t } = useI18n();
  const { mode, toggle } = useTheme();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const nav = useQuery({
    queryKey: ["navigation"],
    queryFn: () => api.get<Navigation>("/api/v1/auth/me/navigation"),
  });

  const items = nav.data?.items ?? [];

  useEffect(() => {
    if (!mobileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen]);

  return (
    <AppShell
      banner={
        user?.is_controller ? (
          <ControllerSessionBanner
            message={t("controller.banner")}
            readOnly={user.read_only}
            readOnlyMessage={t("controller.banner_read_only")}
          />
        ) : undefined
      }
      sidebar={
        <Sidebar
          brand={
            <>
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-primary text-sm font-bold text-sidebar-primary-foreground">
                {t("app.short_name")}
              </span>
              {collapsed ? null : <span className="font-semibold">{t("app.name")}</span>}
            </>
          }
          items={items.map((item) => ({ key: item.key, label: t(item.label_key), href: item.path }))}
          navLabel={t("nav.dashboard")}
          collapsed={collapsed}
          onToggleCollapsed={() => setCollapsed((current) => !current)}
          className={mobileOpen ? "ui-sidebar--open" : undefined}
          renderLink={(item, className) => (
            <NavLink
              to={item.href ?? "/"}
              end={item.href === "/"}
              className={({ isActive }) => (isActive ? `${className} ui-navlink--active` : className)}
              onClick={() => setMobileOpen(false)}
            >
              {collapsed ? <span className="ui-visually-hidden">{item.label}</span> : item.label}
            </NavLink>
          )}
          footer={
            <>
              {nav.isPending ? (
                <Skeleton variant="text" />
              ) : nav.isError ? (
                <p className="px-3 py-2 text-xs text-destructive">{t("common.error")}</p>
              ) : null}
              {/* Below md the top bar only keeps the menu button, so the
                  language, theme and sign-out controls live in the drawer. */}
              {mobileOpen ? (
                <div className="flex flex-col gap-2 p-3 md:hidden">
                  <LanguageSwitch />
                  <ThemePicker />
                  <Button variant="outline" onClick={toggle}>
                    {mode === "dark" ? t("common.theme.light") : t("common.theme.dark")}
                  </Button>
                  <Button variant="ghost" onClick={() => void logout()}>
                    {t("auth.logout")}
                  </Button>
                </div>
              ) : null}
            </>
          }
        />
      }
      topbar={
        <TopBar
          identity={user?.display_name}
          muted={user?.is_controller ? t("controller.session_opened") : user?.email}
          actions={
            <>
              <Button
                variant="outline"
                size="sm"
                className="ui-mobile-only"
                onClick={() => setMobileOpen((current) => !current)}
                aria-expanded={mobileOpen}
                aria-label={t("common.menu")}
              >
                <span aria-hidden="true">☰</span>
              </Button>
              <div className="ui-desktop-only items-center gap-2">
                <LanguageSwitch />
                <span className="ui-wide-only">
                  <ThemePicker />
                </span>
                <Button variant="outline" onClick={toggle}>
                  {mode === "dark" ? t("common.theme.light") : t("common.theme.dark")}
                </Button>
                <Button variant="ghost" onClick={() => void logout()}>
                  {t("auth.logout")}
                </Button>
              </div>
            </>
          }
        />
      }
    >
      {mobileOpen ? (
        <button
          type="button"
          className="ui-nav-scrim"
          aria-label={t("common.close")}
          onClick={() => setMobileOpen(false)}
        />
      ) : null}
      <Outlet />
      {mobileOpen ? null : <ChatPanel />}
    </AppShell>
  );
}

function LanguageSwitch() {
  const { t, locale, languages, setLocale } = useI18n();
  return (
    <select
      aria-label={t("common.language")}
      value={locale}
      onChange={(event) => setLocale(event.target.value)}
      className="ui-select"
    >
      {languages.map((code) => (
        <option key={code} value={code}>
          {t(`settings.enum.${code}`)}
        </option>
      ))}
    </select>
  );
}
