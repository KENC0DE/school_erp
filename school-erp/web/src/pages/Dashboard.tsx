import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Button, EmptyState, ErrorState, LoadingState } from "@erp/ui-web";

import { Badge } from "../components/ui/Badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { api, type Navigation } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

export function DashboardPage() {
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const nav = useQuery({
    queryKey: ["navigation"],
    queryFn: () => api.get<Navigation>("/api/v1/auth/me/navigation"),
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">{t("dashboard.title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("dashboard.welcome", { name: user?.display_name ?? "" })}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("dashboard.modules")}</CardTitle>
          <CardDescription>{t("dashboard.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {nav.isPending ? (
            <LoadingState label={t("common.loading")} rows={2} columns={4} />
          ) : nav.isError ? (
            <ErrorState
              title={t("common.error")}
              retry={
                <Button size="sm" variant="outline" onClick={() => void nav.refetch()}>
                  {t("common.retry")}
                </Button>
              }
            />
          ) : (nav.data?.modules ?? []).length === 0 ? (
            <EmptyState title={t("dashboard.empty")} />
          ) : (
            <div className="flex flex-wrap gap-2">
              {(nav.data?.modules ?? []).map((module) => (
                <Badge key={module}>{module}</Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("dashboard.language_hint")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{locale === "am" ? t("dashboard.amharic_sample") : t("dashboard.subtitle")}</p>
          {nav.data?.items.some((item) => item.key === "sample") ? (
            <Link className="mt-3 inline-block text-sm font-medium text-primary underline" to="/sample">
              {t("sample.title")}
            </Link>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
