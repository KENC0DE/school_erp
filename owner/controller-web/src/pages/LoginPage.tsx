import { ApiRequestError } from "@erp/api-client";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { useT } from "../i18n";
import { useAuth } from "../providers/AuthProvider";

export function LoginPage() {
  const t = useT();
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/schools" replace />;

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/schools", { replace: true });
    } catch (err) {
      if (err instanceof ApiRequestError && err.message) {
        setError(err.message);
      } else {
        setError(t("controller.login.invalid"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("controller.app.brand")} · {t("controller.app.brandSuffix")}
          </div>
          <h1 className="text-xl font-semibold leading-none">{t("controller.login.title")}</h1>
          <CardDescription>{t("controller.login.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4" onSubmit={onSubmit} data-testid="login-form">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="login-email" className="text-sm font-medium">
                {t("controller.login.email")}
              </label>
              <Input
                id="login-email"
                name="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="login-password" className="text-sm font-medium">
                {t("controller.login.password")}
              </label>
              <Input
                id="login-password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
            <Button type="submit" disabled={submitting} data-testid="login-submit">
              {t(submitting ? "controller.login.submitting" : "controller.login.submit")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
