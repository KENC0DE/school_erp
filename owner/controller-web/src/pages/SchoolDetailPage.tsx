import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import { SupportSessionDialog } from "../components/SupportSessionDialog";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { useT, type Translate } from "../i18n";
import { api, API_PREFIX } from "../lib/api";
import { LICENSABLE_MODULES, type School } from "../lib/types";

function ModuleRow({
  moduleKey,
  enabled,
  disabled,
  onToggle,
  t,
}: {
  moduleKey: string;
  enabled: boolean;
  disabled: boolean;
  onToggle: (key: string, next: boolean) => void;
  t: Translate;
}) {
  const inputId = `module-${moduleKey}`;
  return (
    <li
      data-testid={`module-row-${moduleKey}`}
      className="flex items-center justify-between gap-4 border-b border-border py-2 last:border-b-0"
    >
      <label htmlFor={inputId} className="text-sm font-medium capitalize">
        {t("controller.school.modules.toggleLabel", { module: moduleKey })}
      </label>
      <div className="flex items-center gap-3">
        <Badge data-testid={`module-state-${moduleKey}`}>
          {t(
            enabled
              ? "controller.school.modules.enabled"
              : "controller.school.modules.disabled",
          )}
        </Badge>
        <input
          id={inputId}
          type="checkbox"
          role="switch"
          className="h-5 w-5 accent-primary"
          checked={enabled}
          disabled={disabled}
          data-testid={`module-toggle-${moduleKey}`}
          onChange={(event) => onToggle(moduleKey, event.target.checked)}
        />
      </div>
    </li>
  );
}

export function SchoolDetailPage() {
  const t = useT();
  const { schoolId = "" } = useParams();
  const [school, setSchool] = useState<School | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);
  const [pendingModule, setPendingModule] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<School>(`${API_PREFIX}/schools/${schoolId}`);
      setSchool(response);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : t("controller.common.error"));
    } finally {
      setLoading(false);
    }
  }, [schoolId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleModule = async (key: string, nextEnabled: boolean) => {
    if (!school || pendingModule) return;
    const previous = school;
    setToggleError(null);
    setPendingModule(key);
    setSchool({
      ...school,
      modules: nextEnabled
        ? [...school.modules, key].sort()
        : school.modules.filter((module) => module !== key),
    });
    try {
      const updated = await api.patch<School>(`${API_PREFIX}/schools/${school.id}/modules`, {
        key,
        enabled: nextEnabled,
      });
      setSchool(updated);
    } catch (err) {
      setSchool(previous);
      setToggleError(
        err instanceof Error && err.message
          ? err.message
          : t("controller.school.modules.error"),
      );
    } finally {
      setPendingModule(null);
    }
  };

  if (loading) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        {t("controller.common.loading")}
      </p>
    );
  }

  if (error || !school) {
    return (
      <div role="alert" className="flex items-center justify-between gap-4 rounded-md border border-destructive bg-card p-4">
        <span className="text-sm text-destructive">{error ?? t("controller.common.error")}</span>
        <Button variant="outline" onClick={() => void load()}>
          {t("controller.common.retry")}
        </Button>
      </div>
    );
  }

  const enabledModules = new Set(school.modules);

  return (
    <div className="flex flex-col gap-6" data-testid="school-detail">
      <div>
        <Link to="/schools" className="text-sm text-muted-foreground hover:underline">
          {t("controller.school.back")}
        </Link>
      </div>

      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold" data-testid="school-detail-title">
            {school.name}
          </h1>
          <StatusBadge status={school.status} testId="school-detail-status" />
        </div>
        <Button onClick={() => setDialogOpen(true)} data-testid="open-support-session">
          {t("controller.school.openAsAdmin")}
        </Button>
      </header>
      <p className="-mt-4 text-sm text-muted-foreground">{t("controller.school.openAsAdminHint")}</p>

      <Card>
        <CardHeader>
          <CardTitle>{t("controller.school.details")}</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">{t("controller.school.code")}</dt>
              <dd className="font-medium">{school.school_code}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("controller.school.apiUrl")}</dt>
              <dd className="break-all font-medium">{school.api_base_url}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("controller.school.plan")}</dt>
              <dd className="font-medium">{school.plan ?? t("controller.common.none")}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("controller.school.appVersion")}</dt>
              <dd className="font-medium">{school.app_version ?? t("controller.common.none")}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("controller.school.enrollment")}</dt>
              <dd className="font-medium">
                {t(
                  school.enrolled
                    ? "controller.schools.enrolled"
                    : "controller.schools.notEnrolled",
                )}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("controller.school.modules.title")}</CardTitle>
          <p className="text-sm text-muted-foreground">
            {t("controller.school.modules.description")}
          </p>
        </CardHeader>
        <CardContent>
          {toggleError ? (
            <p role="alert" className="mb-3 text-sm text-destructive">
              {toggleError}
            </p>
          ) : null}
          <ul>
            {LICENSABLE_MODULES.map((moduleKey) => (
              <ModuleRow
                key={moduleKey}
                moduleKey={moduleKey}
                enabled={enabledModules.has(moduleKey)}
                disabled={pendingModule !== null}
                onToggle={(key, next) => void toggleModule(key, next)}
                t={t}
              />
            ))}
          </ul>
        </CardContent>
      </Card>

      <SupportSessionDialog
        schoolId={school.id}
        schoolName={school.name}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
      />
    </div>
  );
}
