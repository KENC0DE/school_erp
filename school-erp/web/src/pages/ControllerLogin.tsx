import { useEffect, useRef, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

/**
 * Landing point for "Open as school admin" links issued by the control plane.
 * The support token is exchanged for a short-lived, audited school session.
 */
export function ControllerLoginPage() {
  const { t } = useI18n();
  const { user, controllerLogin } = useAuth();
  const [params] = useSearchParams();
  const [failed, setFailed] = useState(false);
  const attempted = useRef(false);
  const token = params.get("token");
  const reason = params.get("reason");

  useEffect(() => {
    if (attempted.current || !token) return;
    attempted.current = true;
    controllerLogin(token).catch(() => setFailed(true));
  }, [controllerLogin, token]);

  if (user) return <Navigate to="/" replace />;

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{t("controller.session_opened")}</CardTitle>
          <CardDescription>{reason ?? t("common.loading")}</CardDescription>
        </CardHeader>
        <CardContent>
          {failed || !token ? (
            <p role="alert" className="text-sm text-destructive">
              {t("controller.session_failed")}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
