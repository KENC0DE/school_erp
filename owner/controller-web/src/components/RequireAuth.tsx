import { Navigate, Outlet } from "react-router-dom";

import { useT } from "../i18n";
import { useAuth } from "../providers/AuthProvider";

export function RequireAuth() {
  const { user, loading } = useAuth();
  const t = useT();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground" role="status">
        {t("controller.common.loading")}
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
