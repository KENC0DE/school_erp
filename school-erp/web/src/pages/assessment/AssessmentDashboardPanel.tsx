import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Select,
  type Column,
} from "@erp/ui-web";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { useSections } from "../academics/queries";
import {
  ASSESSMENT,
  useAssessmentDashboard,
  useAssessmentSubjects,
  useAssessmentYears,
} from "./queries";
import type { DashboardAnomaly, DashboardRow, ReminderResult } from "./types";

interface DashboardPanelProps {
  canManage: boolean;
}

function shortDate(value: string | null): string {
  return value ? value.slice(0, 10) : "";
}

export function AssessmentDashboardPanel({ canManage }: DashboardPanelProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const years = useAssessmentYears();
  const subjects = useAssessmentSubjects(true);

  const [yearId, setYearId] = useState("");
  const [termId, setTermId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (yearId || !years.data) return;
    setYearId(years.data.current_year_id ?? years.data.items[0]?.id ?? "");
  }, [years.data, yearId]);

  const year = years.data?.items.find((item) => item.id === yearId) ?? null;
  const terms = useMemo(() => year?.terms ?? [], [year]);
  const sections = useSections(yearId || null);

  useEffect(() => {
    if (!terms.length) return;
    if (terms.some((item) => item.id === termId)) return;
    setTermId(
      terms.find((item) => item.id === year?.current_term_id)?.id ??
        terms[0]?.id ??
        "",
    );
  }, [terms, termId, year]);

  const query = useAssessmentDashboard(
    yearId || null,
    termId || null,
    sectionId || null,
    subjectId || null,
  );

  const remind = useMutation({
    mutationFn: () =>
      api.post<ReminderResult>(`${ASSESSMENT}/dashboard/remind`, {
        year_id: yearId,
        term_id: termId,
        section_id: sectionId || null,
        subject_id: subjectId || null,
      }),
    onSuccess: (result) => {
      if (result.sent === 0) {
        setNotice(t("assessment.dashboard.remind_none"));
      } else if (result.skipped > 0) {
        setNotice(
          t("assessment.dashboard.reminded_skipped", {
            count: result.sent,
            skipped: result.skipped,
          }),
        );
      } else {
        setNotice(t("assessment.dashboard.reminded", { count: result.sent }));
      }
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "dashboard"],
      });
    },
    onError: (error) => {
      setNotice(
        error instanceof ApiRequestError
          ? error.message
          : t("assessment.dashboard.remind_failed"),
      );
    },
  });

  const data = query.data;

  const columns = useMemo<Column<DashboardRow>[]>(
    () => [
      {
        key: "section",
        header: t("assessment.dashboard.section"),
        render: (row) => (
          <span>
            {row.level_name} {row.section_code}
          </span>
        ),
      },
      {
        key: "subject",
        header: t("assessment.dashboard.subject"),
        render: (row) => row.subject_name,
      },
      {
        key: "teacher",
        header: t("assessment.dashboard.teacher"),
        render: (row) =>
          row.teachers.length
            ? row.teachers.map((teacher) => teacher.name).join(", ")
            : "—",
      },
      {
        key: "assessments",
        header: t("assessment.dashboard.assessments"),
        numeric: true,
        render: (row) => row.assessments,
      },
      {
        key: "progress",
        header: t("assessment.dashboard.completion"),
        numeric: true,
        render: (row) => (
          <span
            data-testid={`dashboard-progress-${row.section_code}-${row.subject_id}`}
          >
            <span className="ui-num">
              {row.entered}/{row.expected}
            </span>{" "}
            <Badge
              variant={
                Number(row.completion_percent) >= 100 ? "success" : "warning"
              }
            >
              {row.completion_percent}%
            </Badge>
          </span>
        ),
      },
      {
        key: "deadline",
        header: t("assessment.dashboard.deadline"),
        render: (row) =>
          row.deadline
            ? shortDate(row.deadline)
            : t("assessment.dashboard.no_deadline"),
      },
      {
        key: "status",
        header: t("assessment.dashboard.status"),
        render: (row) => (
          <span className="flex flex-wrap items-center gap-2">
            <Badge variant={row.status === "published" ? "info" : "neutral"}>
              {t(`assessment.dashboard.status.${row.status}`)}
            </Badge>
            {row.overdue ? (
              <Badge variant="danger">
                {t("assessment.dashboard.overdue")}
              </Badge>
            ) : null}
          </span>
        ),
      },
    ],
    [t],
  );

  function anomalyText(anomaly: DashboardAnomaly): string {
    if (anomaly.kind === "identical") {
      return t("assessment.dashboard.anomaly.identical", {
        value: anomaly.value ?? "",
      });
    }
    return t("assessment.dashboard.anomaly.average_outlier", {
      average: anomaly.average_percent ?? "",
    });
  }

  function anomalyHint(anomaly: DashboardAnomaly): string {
    if (anomaly.kind === "identical") {
      return t("assessment.dashboard.anomaly.identical_hint", {
        count: anomaly.count,
      });
    }
    return t("assessment.dashboard.anomaly.average_hint", {
      norm: anomaly.norm_percent ?? "",
    });
  }

  if (years.isLoading) {
    return <LoadingState label={t("assessment.dashboard.title")} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("assessment.dashboard.title")}</CardTitle>
          <CardDescription>{t("assessment.dashboard.intro")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <Field label={t("assessment.dashboard.year")}>
              <Select
                data-testid="dashboard-year"
                value={yearId}
                onChange={(event) => {
                  setYearId(event.target.value);
                  setTermId("");
                  setSectionId("");
                }}
              >
                {(years.data?.items ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("assessment.dashboard.term")}>
              <Select
                data-testid="dashboard-term"
                value={termId}
                onChange={(event) => setTermId(event.target.value)}
              >
                {terms.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("assessment.dashboard.section")}>
              <Select
                data-testid="dashboard-section"
                value={sectionId}
                onChange={(event) => setSectionId(event.target.value)}
              >
                <option value="">—</option>
                {(sections.data?.items ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.level_name} {item.code}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("assessment.dashboard.subject")}>
              <Select
                data-testid="dashboard-subject"
                value={subjectId}
                onChange={(event) => setSubjectId(event.target.value)}
              >
                <option value="">—</option>
                {(subjects.data?.items ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {canManage ? (
            <div className="mt-4 flex items-center gap-3">
              <Button
                data-testid="dashboard-remind"
                disabled={!yearId || !termId || remind.isPending}
                onClick={() => {
                  setNotice(null);
                  remind.mutate();
                }}
              >
                {remind.isPending
                  ? t("assessment.dashboard.reminding")
                  : t("assessment.dashboard.remind")}
              </Button>
              {notice ? (
                <p
                  role="status"
                  className="text-sm text-muted-foreground"
                  data-testid="dashboard-notice"
                >
                  {notice}
                </p>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {query.isError && !data ? (
        <ErrorState
          title={t("assessment.dashboard.load_error")}
          retry={
            <Button variant="outline" onClick={() => void query.refetch()}>
              {t("common.retry")}
            </Button>
          }
        />
      ) : null}

      {data ? (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent>
                <p className="ui-help">
                  {t("assessment.dashboard.completion")}
                </p>
                <p
                  className="ui-num text-2xl"
                  data-testid="dashboard-completion"
                >
                  {data.summary.completion_percent}%
                </p>
                <p className="ui-help">
                  {t("assessment.dashboard.summary", {
                    entered: data.summary.entered,
                    expected: data.summary.expected,
                  })}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <p className="ui-help">{t("assessment.dashboard.overdue")}</p>
                <p className="ui-num text-2xl" data-testid="dashboard-overdue">
                  {data.summary.overdue}
                </p>
                <p className="ui-help">
                  {t("assessment.dashboard.summary_sections", {
                    count: data.summary.sections,
                  })}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <p className="ui-help">{t("assessment.dashboard.anomalies")}</p>
                <p
                  className="ui-num text-2xl"
                  data-testid="dashboard-anomalies"
                >
                  {data.summary.anomalies}
                </p>
                <p className="ui-help">
                  {t("assessment.dashboard.anomaly_none")}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <p className="ui-help">
                  {t("assessment.dashboard.assessments")}
                </p>
                <p className="ui-num text-2xl">{data.summary.assessments}</p>
                <p className="ui-help">
                  {t("assessment.dashboard.students")}:{" "}
                  {data.rows.reduce((total, row) => total + row.students, 0)}
                </p>
              </CardContent>
            </Card>
          </div>

          <DataTable
            columns={columns}
            rows={data.rows}
            rowKey={(row) => `${row.section_id}:${row.subject_id}`}
            caption={t("assessment.dashboard.title")}
            emptyTitle={t("assessment.dashboard.empty")}
            emptyDescription={t("assessment.dashboard.empty_hint")}
          />

          <Card>
            <CardHeader>
              <CardTitle>{t("assessment.dashboard.anomalies")}</CardTitle>
              <CardDescription>
                {t("assessment.dashboard.anomaly_none")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.anomalies.length === 0 ? (
                <EmptyState
                  title={t("assessment.dashboard.anomaly_none")}
                  testId="dashboard-anomaly-empty"
                />
              ) : (
                <ul
                  className="flex flex-col gap-3"
                  data-testid="dashboard-anomaly-list"
                >
                  {data.anomalies.map((anomaly) => (
                    <li
                      key={`${anomaly.kind}:${anomaly.assessment_id}`}
                      className="flex flex-wrap items-center gap-3"
                      data-testid={`dashboard-anomaly-${anomaly.kind}`}
                    >
                      <Badge
                        variant={
                          anomaly.kind === "identical" ? "warning" : "danger"
                        }
                      >
                        {anomaly.kind === "identical"
                          ? t("assessment.dashboard.anomaly.identical_badge")
                          : t("assessment.dashboard.anomaly.average_badge")}
                      </Badge>
                      <span className="font-medium">{anomaly.title}</span>
                      <span className="ui-help">
                        {anomaly.section_code} · {anomaly.subject_name}
                      </span>
                      <span>{anomalyText(anomaly)}</span>
                      <span className="ui-help">{anomalyHint(anomaly)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
