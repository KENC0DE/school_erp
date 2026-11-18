import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { Shell } from "./components/Shell";
import { ActivityPage } from "./pages/ActivityPage";
import { AcademicsPage } from "./pages/academics/AcademicsPage";
import { AdmissionsPage } from "./pages/admissions/AdmissionsPage";
import { ApplicationFormPage } from "./pages/admissions/ApplicationFormPage";
import { ApplicationProfilePage } from "./pages/admissions/ApplicationProfilePage";
import { PublicApplicationPage } from "./pages/admissions/PublicApplicationPage";
import { AttendancePage } from "./pages/attendance/AttendancePage";
import { ControllerLoginPage } from "./pages/ControllerLogin";
import { DashboardPage } from "./pages/Dashboard";
import { DesignReferencePage } from "./pages/design/DesignReferencePage";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/Login";
import { ModulesPage } from "./pages/ModulesPage";
import { NotFoundPage } from "./pages/NotFound";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ResetPasswordPage } from "./pages/ResetPassword";
import { RolesPage } from "./pages/RolesPage";
import { SamplePage } from "./pages/SamplePage";
import { SettingsPage } from "./pages/SettingsPage";
import { SetupWizardPage } from "./pages/SetupWizardPage";
import { StaffPage } from "./pages/staff/StaffPage";
import { StaffProfilePage } from "./pages/staff/StaffProfilePage";
import { StudentProfilePage } from "./pages/students/StudentProfilePage";
import { PromotionPage } from "./pages/students/PromotionPage";
import { StudentsPage } from "./pages/students/StudentsPage";
import { ThemeManagerPage } from "./pages/ThemeManagerPage";
import { TranslationsPage } from "./pages/TranslationsPage";
import { UsersPage } from "./pages/UsersPage";
import { AuthProvider, useAuth } from "./providers/AuthProvider";
import { I18nProvider, useI18n } from "./providers/I18nProvider";
import { ThemeProvider } from "./providers/ThemeProvider";

export const appQueryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false },
  },
});

function RequireAuth() {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  const location = useLocation();
  if (loading)
    return (
      <p className="p-6 text-sm text-muted-foreground">{t("common.loading")}</p>
    );
  if (!user)
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
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
      <I18nProvider initialMessages={initialMessages}>
        <AuthProvider>
          <ThemeProvider>{children}</ThemeProvider>
        </AuthProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupWizardPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/controller-login" element={<ControllerLoginPage />} />
      <Route path="/apply" element={<PublicApplicationPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route index element={<DashboardPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="roles" element={<RolesPage />} />
          <Route path="sample" element={<SamplePage />} />
          <Route path="activity" element={<ActivityPage />} />
          <Route path="academics" element={<AcademicsPage />} />
          <Route path="students" element={<StudentsPage />} />
          <Route path="students/promotions" element={<PromotionPage />} />
          <Route path="students/:studentId" element={<StudentProfilePage />} />
          <Route path="staff" element={<StaffPage />} />
          <Route path="staff/:staffId" element={<StaffProfilePage />} />
          <Route path="attendance" element={<AttendancePage />} />
          <Route path="admissions" element={<AdmissionsPage />} />
          <Route
            path="admissions/new"
            element={<ApplicationFormPage mode="new" />}
          />
          <Route path="admissions/:id" element={<ApplicationProfilePage />} />
          <Route
            path="admissions/:id/edit"
            element={<ApplicationFormPage mode="edit" />}
          />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="settings/modules" element={<ModulesPage />} />
          <Route path="settings/languages" element={<TranslationsPage />} />
          <Route path="settings/themes" element={<ThemeManagerPage />} />
          <Route path="design" element={<DesignReferencePage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export function App({
  initialMessages,
}: {
  initialMessages?: Record<string, string>;
}) {
  return (
    <AppProviders initialMessages={initialMessages}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AppProviders>
  );
}
