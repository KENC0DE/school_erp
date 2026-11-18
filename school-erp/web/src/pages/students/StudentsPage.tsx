import { ApiRequestError } from "@erp/api-client";
import { EmptyState, ErrorState, LoadingState, Page, PageHeader } from "@erp/ui-web";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import {
  EMPTY_FILTERS,
  loadSavedViews,
  newViewId,
  persistSavedViews,
} from "./savedViews";
import { hasPermission, useLevels, useSections, useStudents, useYears } from "./queries";
import { StudentRegisterDialog } from "./StudentRegisterDialog";
import type { SavedView, StudentFilters, StudentStatus, StudentSummary } from "./types";

const STATUSES: StudentStatus[] = [
  "applicant",
  "active",
  "promoted",
  "repeating",
  "transferred_out",
  "withdrawn",
  "graduated",
  "alumni",
];

function statusVariant(status: StudentStatus): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "active") return "success";
  if (status === "applicant") return "info";
  if (status === "repeating" || status === "promoted") return "warning";
  if (status === "withdrawn" || status === "transferred_out") return "danger";
  return "neutral";
}

function emptyFilters(): StudentFilters {
  return { ...EMPTY_FILTERS };
}

export function StudentsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const canView = hasPermission(user?.permissions, "students.view");
  const canManage = hasPermission(user?.permissions, "students.manage");

  const [filters, setFilters] = useState<StudentFilters>(emptyFilters);
  const [draftQuery, setDraftQuery] = useState("");
  const [views, setViews] = useState<SavedView[]>(() => loadSavedViews());
  const [selectedView, setSelectedView] = useState("");
  const [savingView, setSavingView] = useState(false);
  const [viewName, setViewName] = useState("");
  const [registering, setRegistering] = useState(false);
  const [registered, setRegistered] = useState<StudentSummary | null>(null);

  const years = useYears();
  const levels = useLevels();
  const sections = useSections(filters.year_id, filters.level_id);
  const students = useStudents(filters, null);

  if (!canView) {
    return (
      <Page>
        <Card>
          <CardContent className="p-6">
            <EmptyState title={t("students.permission_denied")} />
          </CardContent>
        </Card>
      </Page>
    );
  }

  const rows = students.data?.items ?? [];

  function applyFilters(next: StudentFilters) {
    setFilters(next);
    setDraftQuery(next.q);
    setSelectedView("");
    setRegistered(null);
  }

  function onSearch(event: FormEvent) {
    event.preventDefault();
    setFilters((current) => ({ ...current, q: draftQuery.trim() }));
  }

  function saveView() {
    const name = viewName.trim();
    if (!name) return;
    const next = [...views, { id: newViewId(), name, filters: { ...filters, q: draftQuery.trim() } }];
    setViews(next);
    persistSavedViews(next);
    setSavingView(false);
    setViewName("");
  }

  function applyView(id: string) {
    setSelectedView(id);
    const view = views.find((item) => item.id === id);
    if (view) applyFilters({ ...EMPTY_FILTERS, ...view.filters });
  }

  function removeView() {
    if (!selectedView) return;
    const next = views.filter((item) => item.id !== selectedView);
    setViews(next);
    persistSavedViews(next);
    setSelectedView("");
  }

  return (
    <Page>
      <PageHeader
        title={t("students.title")}
        description={t("students.intro")}
        actions={
          canManage ? (
            <Button onClick={() => setRegistering(true)} data-testid="student-register-open">
              {t("students.register.open")}
            </Button>
          ) : undefined
        }
      />

      {registered ? (
        <p className="text-sm text-primary" role="status" data-testid="student-registered">
          {t("students.register.created", { name: registered.person.full_name })}{" "}
          <Link className="ui-link" to={`/students/${registered.id}`}>
            {t("students.open_profile")}
          </Link>
        </p>
      ) : null}

      <Card>
        <CardContent className="space-y-4 p-4">
          <form className="flex flex-wrap items-end gap-3" onSubmit={onSearch}>
            <label className="min-w-60 flex-1 space-y-1 text-sm">
              <span className="font-medium">{t("students.search.label")}</span>
              <Input
                data-testid="student-search"
                value={draftQuery}
                placeholder={t("students.search.placeholder")}
                onChange={(event) => setDraftQuery(event.target.value)}
              />
            </label>
            <Button type="submit" variant="outline">
              {t("students.search.action")}
            </Button>
          </form>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("students.status")}</span>
              <select
                className="ui-select"
                data-testid="student-status-filter"
                value={filters.status}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    status: event.target.value as StudentFilters["status"],
                  }))
                }
              >
                <option value="">{t("students.filter.all_statuses")}</option>
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {t(`students.status.${status}`)}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("students.enrollment.year")}</span>
              <select
                className="ui-select"
                data-testid="student-year-filter"
                value={filters.year_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    year_id: event.target.value,
                    level_id: "",
                    section_id: "",
                  }))
                }
              >
                <option value="">{t("students.filter.all_years")}</option>
                {(years.data?.items ?? []).map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("students.enrollment.level")}</span>
              <select
                className="ui-select"
                data-testid="student-level-filter"
                value={filters.level_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    level_id: event.target.value,
                    section_id: "",
                  }))
                }
              >
                <option value="">{t("students.filter.all_levels")}</option>
                {(levels.data?.items ?? []).map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("students.enrollment.section")}</span>
              <select
                className="ui-select"
                data-testid="student-section-filter"
                value={filters.section_id}
                disabled={!filters.year_id || !filters.level_id}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, section_id: event.target.value }))
                }
              >
                <option value="">{t("students.filter.all_sections")}</option>
                {(sections.data?.items ?? []).map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.code}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
            <label className="min-w-48 space-y-1 text-sm">
              <span className="font-medium">{t("students.views.title")}</span>
              <select
                className="ui-select"
                data-testid="student-view-select"
                value={selectedView}
                onChange={(event) => applyView(event.target.value)}
              >
                <option value="">{t("students.views.none")}</option>
                {views.map((view) => (
                  <option key={view.id} value={view.id}>
                    {view.name}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="outline" onClick={() => setSavingView(true)}>
              {t("students.views.save")}
            </Button>
            {selectedView ? (
              <Button variant="ghost" onClick={removeView}>
                {t("students.views.delete")}
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {savingView ? (
        <Card>
          <CardContent className="flex flex-wrap items-end gap-2 p-4">
            <label className="min-w-56 flex-1 space-y-1 text-sm">
              <span className="font-medium">{t("students.views.name")}</span>
              <Input
                data-testid="student-view-name"
                value={viewName}
                onChange={(event) => setViewName(event.target.value)}
              />
            </label>
            <Button onClick={saveView} disabled={!viewName.trim()}>
              {t("students.views.save_action")}
            </Button>
            <Button variant="ghost" onClick={() => setSavingView(false)}>
              {t("common.cancel")}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {students.isPending ? (
        <LoadingState label={t("students.loading")} testId="students-loading" />
      ) : students.isError ? (
        <Card>
          <CardContent className="p-6">
            <ErrorState
              title={t("students.load_error")}
              requestId={requestIdOf(students.error)}
              requestIdLabel={t("common.request_id")}
              retry={
                <Button variant="outline" onClick={() => void students.refetch()}>
                  {t("common.retry")}
                </Button>
              }
              testId="students-error"
            />
          </CardContent>
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="p-6">
            <EmptyState
              title={t("students.empty")}
              description={t("students.empty_hint")}
              testId="students-empty"
              action={
                canManage ? (
                  <Button onClick={() => setRegistering(true)}>{t("students.register.open")}</Button>
                ) : undefined
              }
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0" tabIndex={0} role="region" aria-label={t("students.title")}>
            <table className="ui-table" data-testid="students-table">
              <caption className="ui-visually-hidden">{t("students.title")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("students.number")}</th>
                  <th scope="col">{t("students.person")}</th>
                  <th scope="col">{t("students.enrollment")}</th>
                  <th scope="col">{t("students.status")}</th>
                  <th scope="col">{t("students.admission_date")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((student) => (
                  <tr key={student.id} data-testid={`student-row-${student.id}`}>
                    <td className="ui-num">
                      <Link className="ui-link" to={`/students/${student.id}`}>
                        {student.student_number}
                      </Link>
                    </td>
                    <td>
                      <Link className="ui-link" to={`/students/${student.id}`}>
                        {student.person.full_name}
                      </Link>
                      {student.person.given_name_am ? (
                        <span className="block text-xs text-muted-foreground" lang="am" dir="auto">
                          {[
                            student.person.given_name_am,
                            student.person.father_name_am,
                            student.person.grandfather_name_am,
                          ]
                            .filter(Boolean)
                            .join(" ")}
                        </span>
                      ) : null}
                    </td>
                    <td>
                      {student.enrollment
                        ? [
                            student.enrollment.level_name,
                            student.enrollment.section_code,
                          ]
                            .filter(Boolean)
                            .join(" · ")
                        : t("students.not_enrolled")}
                    </td>
                    <td>
                      <Badge variant={statusVariant(student.status)}>
                        {t(`students.status.${student.status}`)}
                      </Badge>
                    </td>
                    <td>{student.admission_date ?? t("students.not_set")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
          <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
            {t("students.count", { count: students.data?.total ?? rows.length })}
          </p>
        </Card>
      )}

      {students.isError && students.error instanceof ApiRequestError ? (
        <p className="text-sm text-destructive">{students.error.message}</p>
      ) : null}

      <StudentRegisterDialog
        open={registering}
        onClose={() => setRegistering(false)}
        onRegistered={(student) => {
          setRegistering(false);
          setRegistered(student);
          void students.refetch();
        }}
      />
    </Page>
  );
}
