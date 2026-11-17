import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { Shell } from "./components/Shell";
import { ControllerLoginPage } from "./pages/ControllerLogin";
import { DashboardPage } from "./pages/Dashboard";
import { LoginPage } from "./pages/Login";
import { NotFoundPage } from "./pages/NotFound";
import { ResetPasswordPage } from "./pages/ResetPassword";
import { RolesPage } from "./pages/RolesPage";
import { SamplePage } from "./pages/SamplePage";
import { SettingsPage } from "./pages/SettingsPage";
import { UsersPage } from "./pages/UsersPage";
import { AuthProvider, useAuth } from "./providers/AuthProvider";
import { I18nProvider, useI18n } from "./providers/I18nProvider";
import { ThemeProvider } from "./providers/ThemeProvider";

export const appQueryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
});

function RequireAuth() {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  const location = useLocation();
  if (loading) return <p className="p-6 text-sm text-muted-foreground">{t("common.loading")}</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export function AppProviders({
  children,
  initialMessages,
  queryClient = appQueryClient,
}: {
  children: ReactNode;
  initialMessages?: Record<string, string>;
  queryClient?: QueryClient;
}) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <I18nProvider initialMessages={initialMessages}>
          <AuthProvider>{children}</AuthProvider>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/controller-login" element={<ControllerLoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route index element={<DashboardPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="roles" element={<RolesPage />} />
          <Route path="sample" element={<SamplePage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export function App({ initialMessages }: { initialMessages?: Record<string, string> }) {
  return (
    <AppProviders initialMessages={initialMessages}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AppProviders>
  );
}
