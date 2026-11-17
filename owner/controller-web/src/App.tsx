import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth } from "./components/RequireAuth";
import { Shell } from "./components/Shell";
import { useT } from "./i18n";
import { LoginPage } from "./pages/LoginPage";
import { SchoolDetailPage } from "./pages/SchoolDetailPage";
import { SchoolsPage } from "./pages/SchoolsPage";
import { VaultPage } from "./pages/VaultPage";
import { AuthProvider } from "./providers/AuthProvider";
import { ThemeProvider } from "./providers/ThemeProvider";

function DocumentTitle() {
  const t = useT();
  useEffect(() => {
    document.title = t("controller.app.title");
  }, [t]);
  return null;
}

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <DocumentTitle />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route element={<Shell />}>
                <Route path="/" element={<Navigate to="/schools" replace />} />
                <Route path="/schools" element={<SchoolsPage />} />
                <Route path="/schools/:schoolId" element={<SchoolDetailPage />} />
                <Route path="/vault" element={<VaultPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
