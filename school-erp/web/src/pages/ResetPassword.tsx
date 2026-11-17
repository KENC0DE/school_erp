import { ApiRequestError } from "@erp/api-client";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { api } from "../lib/api";
import { useI18n } from "../providers/I18nProvider";

const ERROR_KEYS: Record<string, string> = {
  INVALID_RESET_TOKEN: "error.invalid_reset_token",
  WEAK_PASSWORD: "error.weak_password",
  RATE_LIMITED: "error.rate_limited",
};

export function ResetPasswordPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [mismatch, setMismatch] = useState(false);

  const reset = useMutation({
    mutationFn: () =>
      api.post("/api/v1/auth/reset-password", { token, new_password: password }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirmation) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    reset.mutate();
  }

  const error = reset.error;
  const errorKey = error instanceof ApiRequestError ? ERROR_KEYS[error.code] : undefined;
  const errorMessage = error
    ? t(errorKey ?? (error instanceof ApiRequestError ? error.message : "common.error"))
    : null;

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
      <Card className="w-full max-w-md" data-testid="reset-password-page">
        <CardHeader>
          <CardTitle>{t("auth.reset_password")}</CardTitle>
          <CardDescription>{t("auth.reset_password_hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          {reset.isSuccess ? (
            <div className="space-y-3">
              <p className="text-sm text-primary">{t("auth.reset_password_success")}</p>
              <Link className="text-sm font-medium text-primary underline" to="/login">
                {t("auth.back_to_sign_in")}
              </Link>
            </div>
          ) : (
            <form className="space-y-3" onSubmit={submit}>
              <label className="space-y-1 text-sm">
                <span className="font-medium">{t("auth.new_password")}</span>
                <Input
                  aria-label={t("auth.new_password")}
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  required
                  minLength={12}
                  disabled={reset.isPending}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium">{t("auth.confirm_password")}</span>
                <Input
                  aria-label={t("auth.confirm_password")}
                  type="password"
                  autoComplete="new-password"
                  value={confirmation}
                  required
                  minLength={12}
                  disabled={reset.isPending}
                  onChange={(event) => setConfirmation(event.target.value)}
                />
              </label>
              {mismatch ? <p className="text-sm text-destructive">{t("auth.passwords_mismatch")}</p> : null}
              {!token ? (
                <p className="text-sm text-destructive">{t("error.invalid_reset_token")}</p>
              ) : null}
              {errorMessage ? (
                <p role="alert" className="text-sm text-destructive">
                  {errorMessage}
                </p>
              ) : null}
              <Button type="submit" disabled={reset.isPending || !token}>
                {t("auth.reset_password_submit")}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
