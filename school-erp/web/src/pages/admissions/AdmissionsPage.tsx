import { EmptyState, ErrorState, LoadingState, Page, PageHeader } from "@erp/ui-web";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { hasPermission, useLevels, useYears } from "../students/queries";
import { useAdmissions } from "./queries";
import type { AdmissionStatus, ApplicationFilters } from "./types";

const STATUSES: AdmissionStatus[] = [
  "applied",
  "reviewed",
  "test",
  "offered",
  "accepted",
  "enrolled",
  "rejected",
  "withdrawn",
];

const EMPTY_FILTERS: ApplicationFilters = { q: "", status: "", year_id: "", level_id: "" };

function statusVariant(status: AdmissionStatus): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "accepted" || status === "enrolled") return "success";
  if (status === "offered" || status === "test") return "warning";
  if (status === "rejected" || status === "withdrawn") return "danger";
  if (status === "reviewed") return "info";
  return "neutral";
}

function amharicName(person: { given_name_am: string | null; father_name_am: string | null; grandfather_name_am: string | null }) {
  return [person.given_name_am, person.father_name_am, person.grandfather_name_am]
    .filter(Boolean)
    .join(" ");
}

export function AdmissionsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const canView = hasPermission(user?.permissions, "admissions.view");
  const canManage = hasPermission(user?.permissions, "admissions.manage");

  const navigate = useNavigate();
  const [filters, setFilters] = useState<ApplicationFilters>({ ...EMPTY_FILTERS });
  const [draftQuery, setDraftQuery] = useState("");

  const years = useYears();
  const levels = useLevels();
  const applications = useAdmissions(filters);

  if (!canView) {
    return (
      <Page>
        <Card>
          <CardContent className="p-6">
            <EmptyState title={t("admissions.permission_denied")} />
          </CardContent>
        </Card>
      </Page>
    );
  }

  const rows = applications.data?.items ?? [];

  function onSearch(event: FormEvent) {
    event.preventDefault();
    setFilters((current) => ({ ...current, q: draftQuery.trim() }));
  }

  return (
    <Page>
      <PageHeader
        title={t("admissions.title")}
        description={t("admissions.intro")}
        actions={
          canManage ? (
            <Button data-testid="admission-new" onClick={() => navigate("/admissions/new")}>
              {t("admissions.new.submit")}
            </Button>
          ) : undefined
        }
      />

      <Card>
        <CardContent className="space-y-4 p-4">
          <form className="flex flex-wrap items-end gap-3" onSubmit={onSearch}>
            <label className="min-w-60 flex-1 space-y-1 text-sm">
              <span className="font-medium">{t("admissions.search.label")}</span>
              <Input
                data-testid="admission-search"
                value={draftQuery}
                placeholder={t("admissions.search.placeholder")}
                onChange={(event) => setDraftQuery(event.target.value)}
              />
            </label>
            <Button type="submit" variant="outline">
              {t("admissions.search.action")}
            </Button>
          </form>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("admissions.status")}</span>
              <select
                className="ui-select"
                data-testid="admission-status-filter"
                value={filters.status}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    status: event.target.value as ApplicationFilters["status"],
                  }))
                }
              >
                <option value="">{t("admissions.filter.all_statuses")}</option>
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {t(`admissions.status.${status}`)}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("admissions.year")}</span>
              <select
                className="ui-select"
                data-testid="admission-year-filter"
                value={filters.year_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    year_id: event.target.value,
                    level_id: "",
                  }))
                }
              >
                <option value="">{t("admissions.filter.all_years")}</option>
                {(years.data?.items ?? []).map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("admissions.level")}</span>
              <select
                className="ui-select"
                data-testid="admission-level-filter"
                value={filters.level_id}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, level_id: event.target.value }))
                }
              >
                <option value="">{t("admissions.filter.all_levels")}</option>
                {(levels.data?.items ?? []).map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </CardContent>
      </Card>

      {applications.isPending ? (
        <LoadingState label={t("admissions.loading")} testId="admissions-loading" />
      ) : applications.isError ? (
        <Card>
          <CardContent className="p-6">
            <ErrorState
              title={t("admissions.load_error")}
              requestId={requestIdOf(applications.error)}
              requestIdLabel={t("common.request_id")}
              retry={
                <Button variant="outline" onClick={() => void applications.refetch()}>
                  {t("common.retry")}
                </Button>
              }
              testId="admissions-error"
            />
          </CardContent>
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="p-6">
            <EmptyState
              title={t("admissions.empty")}
              description={t("admissions.empty_hint")}
              testId="admissions-empty"
              action={
                canManage ? (
                  <Button onClick={() => navigate("/admissions/new")}>
                    {t("admissions.new.submit")}
                  </Button>
                ) : undefined
              }
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent
            className="overflow-x-auto p-0"
            tabIndex={0}
            role="region"
            aria-label={t("admissions.title")}
          >
            <table className="ui-table" data-testid="admissions-table">
              <caption className="ui-visually-hidden">{t("admissions.title")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("admissions.application_number")}</th>
                  <th scope="col">{t("admissions.person")}</th>
                  <th scope="col">{t("admissions.level")}</th>
                  <th scope="col">{t("admissions.status")}</th>
                  <th scope="col">{t("admissions.source")}</th>
                  <th scope="col">{t("admissions.applied_on")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((application) => (
                  <tr key={application.id} data-testid={`admission-row-${application.id}`}>
                    <td className="ui-num">
                      <Link className="ui-link" to={`/admissions/${application.id}`}>
                        {application.application_number}
                      </Link>
                    </td>
                    <td>
                      <Link className="ui-link" to={`/admissions/${application.id}`}>
                        {application.person.full_name}
                      </Link>
                      {amharicName(application.person) ? (
                        <span className="block text-xs text-muted-foreground" lang="am" dir="auto">
                          {amharicName(application.person)}
                        </span>
                      ) : null}
                    </td>
                    <td>
                      {[application.level_name, application.section_code]
                        .filter(Boolean)
                        .join(" · ")}
                    </td>
                    <td>
                      <Badge variant={statusVariant(application.status)}>
                        {t(`admissions.status.${application.status}`)}
                      </Badge>
                    </td>
                    <td>{t(`admissions.source.${application.source}`)}</td>
                    <td>{application.applied_on ?? t("admissions.not_set")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
          <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
            {t("admissions.count", { count: applications.data?.total ?? rows.length })}
          </p>
        </Card>
      )}
    </Page>
  );
}
