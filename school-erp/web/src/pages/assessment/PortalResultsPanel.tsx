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
import { useMemo, useState } from "react";

import { useI18n } from "../../providers/I18nProvider";
import { useAssessmentYears, usePortalResults } from "./queries";
import type { PortalChild, PortalResult, SubjectResult } from "./types";

function shortDate(value: string): string {
  return value.slice(0, 10);
}

function rankText(rank: number | null, size: number | null): string {
  if (rank === null) return "—";
  return size === null ? String(rank) : `${rank}/${size}`;
}

function ChildResults({ child }: { child: PortalChild }) {
  const { t } = useI18n();

  const columns = useMemo<Column<SubjectResult>[]>(
    () => [
      {
        key: "subject",
        header: t("assessment.portal.subject"),
        render: (row) => row.subject_name,
      },
      {
        key: "total",
        header: t("assessment.portal.total"),
        numeric: true,
        render: (row) => (
          <span className="ui-num">
            {row.total}/{row.out_of}
          </span>
        ),
      },
      {
        key: "percent",
        header: t("assessment.portal.percent"),
        numeric: true,
        render: (row) => <span className="ui-num">{row.percent}%</span>,
      },
      {
        key: "grade",
        header: t("assessment.portal.grade"),
        render: (row) => (
          <span>
            {row.grade_label ?? "—"}
            {row.grade_remark ? (
              <span className="ui-help"> · {row.grade_remark}</span>
            ) : null}
          </span>
        ),
      },
      {
        key: "rank",
        header: t("assessment.portal.rank"),
        numeric: true,
        render: (row) => rankText(row.rank, row.rank_size),
      },
      {
        key: "pass",
        header: "",
        render: (row) => (
          <Badge variant={row.is_pass ? "success" : "danger"}>
            {row.is_pass
              ? t("assessment.portal.pass")
              : t("assessment.portal.fail")}
          </Badge>
        ),
      },
    ],
    [t],
  );

  function sheet(result: PortalResult) {
    const value = result.result;
    return (
      <Card key={result.snapshot_id}>
        <CardHeader>
          <CardTitle>
            {result.kind === "year"
              ? t("assessment.portal.year_result")
              : t("assessment.portal.term_result", {
                  term: result.term_name ?? result.year_code,
                })}
          </CardTitle>
          <CardDescription>
            {result.level_name} {result.section_code} ·{" "}
            {t("assessment.portal.published", {
              date: shortDate(result.published_at),
            })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={columns}
            rows={value.subjects}
            rowKey={(row) => row.subject_id}
            caption={t("assessment.portal.subject")}
            emptyTitle={t("assessment.portal.empty")}
            emptyDescription={t("assessment.portal.empty_hint")}
            footer={
              <div className="flex flex-wrap items-center gap-3">
                <span className="ui-help">
                  {t("assessment.portal.overall")}
                </span>
                <span className="ui-num">
                  {t("assessment.portal.of", {
                    total: value.total,
                    out_of: value.out_of,
                  })}
                </span>
                <span className="ui-num">{value.percent}%</span>
                {value.grade_label ? (
                  <Badge variant="info">{value.grade_label}</Badge>
                ) : null}
                <Badge variant={value.is_pass ? "success" : "danger"}>
                  {value.is_pass
                    ? t("assessment.portal.pass")
                    : t("assessment.portal.fail")}
                </Badge>
                {value.rank !== null ? (
                  <span className="ui-help">
                    {t("assessment.portal.rank")}{" "}
                    {rankText(value.rank, value.rank_size)}
                  </span>
                ) : null}
              </div>
            }
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <section className="flex flex-col gap-4" data-testid="portal-child">
      <div>
        <h2 className="text-lg font-semibold">{child.student_name}</h2>
        <p className="ui-help" data-testid="portal-child-number">
          {child.student_number}
        </p>
      </div>
      {child.results.map(sheet)}
    </section>
  );
}

export function PortalResultsPanel() {
  const { t } = useI18n();
  const years = useAssessmentYears();
  const [yearId, setYearId] = useState("");

  // Default to the current year without a second fetch: the query only starts
  // once the year list is known, so the empty state cannot flash stale.
  const activeYearId =
    yearId || years.data?.current_year_id || years.data?.items[0]?.id || "";
  const query = usePortalResults(activeYearId || null);
  const children = query.data?.children ?? [];

  if (years.isLoading) {
    return <LoadingState label={t("assessment.portal.title")} />;
  }

  return (
    <div className="flex flex-col gap-6" data-testid="portal-results">
      <Card>
        <CardHeader>
          <CardTitle>{t("assessment.portal.title")}</CardTitle>
          <CardDescription>{t("assessment.portal.intro")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Field label={t("assessment.portal.year")}>
            <Select
              data-testid="portal-year"
              value={activeYearId}
              onChange={(event) => setYearId(event.target.value)}
            >
              {(years.data?.items ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </Field>
        </CardContent>
      </Card>

      {query.isError ? (
        <ErrorState
          title={t("assessment.portal.load_error")}
          retry={
            <Button variant="outline" onClick={() => void query.refetch()}>
              {t("common.retry")}
            </Button>
          }
        />
      ) : null}

      {query.isLoading ? (
        <LoadingState label={t("assessment.portal.title")} />
      ) : null}

      {!query.isLoading && !query.isError && children.length === 0 ? (
        <EmptyState
          title={t("assessment.portal.empty")}
          description={t("assessment.portal.empty_hint")}
          testId="portal-empty"
        />
      ) : null}

      {children.map((child) => (
        <ChildResults key={child.student_id} child={child} />
      ))}
    </div>
  );
}
