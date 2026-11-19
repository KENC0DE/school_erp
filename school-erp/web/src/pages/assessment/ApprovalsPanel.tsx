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
  Dialog,
  ErrorState,
  Field,
  LoadingState,
  Select,
  Textarea,
  type Column,
} from "@erp/ui-web";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import {
  ASSESSMENT,
  useApprovalAssessments,
  useApprovalSubmissions,
  useAssessmentYears,
  useMarkSheets,
} from "./queries";
import type { Submission } from "./types";

const STATUSES = [
  "submitted",
  "approved",
  "published",
  "locked",
  "draft",
  "all",
] as const;

type StatusFilter = (typeof STATUSES)[number];
type Action = "approve" | "reject" | "publish";

interface ApprovalsPanelProps {
  canApprove: boolean;
  canPublish: boolean;
}

const STATUS_VARIANT: Record<
  Submission["status"],
  "neutral" | "success" | "warning" | "danger" | "info"
> = {
  draft: "neutral",
  submitted: "warning",
  approved: "info",
  published: "success",
  locked: "neutral",
};

function shortDate(value: string | null): string {
  return value ? value.slice(0, 10) : "—";
}

export function ApprovalsPanel({
  canApprove,
  canPublish,
}: ApprovalsPanelProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const years = useAssessmentYears();

  const [yearId, setYearId] = useState("");
  const [termId, setTermId] = useState("");
  const [status, setStatus] = useState<StatusFilter>("submitted");
  const [selected, setSelected] = useState<Submission | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (yearId || !years.data) return;
    setYearId(years.data.current_year_id ?? years.data.items[0]?.id ?? "");
  }, [years.data, yearId]);

  const year = years.data?.items.find((item) => item.id === yearId) ?? null;
  const terms = useMemo(() => year?.terms ?? [], [year]);

  useEffect(() => {
    if (!terms.length) return;
    if (terms.some((item) => item.id === termId)) return;
    setTermId(
      terms.find((item) => item.id === year?.current_term_id)?.id ??
        terms[0]?.id ??
        "",
    );
  }, [terms, termId, year]);

  const submissions = useApprovalSubmissions(
    yearId || null,
    termId || null,
    status,
  );

  const assessments = useApprovalAssessments(
    selected ? yearId || null : null,
    selected ? termId || null : null,
    selected?.section_id ?? null,
    selected?.subject_id ?? null,
  );
  const assessmentItems = assessments.data?.items ?? [];
  const sheets = useMarkSheets(assessmentItems.map((item) => item.id));

  const transition = useMutation({
    mutationFn: (action: Action) =>
      api.post<Submission>(
        `${ASSESSMENT}/submissions/${selected?.id}/${action}`,
        {
          row_version: selected?.row_version ?? null,
          note: comment.trim() || null,
        },
      ),
    onSuccess: (_updated, action) => {
      setNotice(
        action === "approve"
          ? t("assessment.approvals.approved")
          : action === "reject"
            ? t("assessment.approvals.rejected")
            : t("assessment.approvals.published"),
      );
      closeReview();
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "approval-submissions"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "approval-assessments"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["assessment", "dashboard"],
      });
    },
    onError: (cause) => {
      setError(
        cause instanceof ApiRequestError
          ? cause.message
          : t("assessment.approvals.failed"),
      );
    },
  });

  function closeReview() {
    setSelected(null);
    setComment("");
    setError(null);
  }

  const columns = useMemo<Column<Submission>[]>(
    () => [
      {
        key: "section",
        header: t("assessment.marks.section"),
        render: (row) => row.section_code,
      },
      {
        key: "subject",
        header: t("assessment.marks.subject"),
        render: (row) => row.subject_name,
      },
      {
        key: "marks",
        header: t("assessment.approvals.marks"),
        numeric: true,
        render: (row) =>
          t("assessment.approvals.entered", {
            entered: row.entered,
            total: row.scores,
          }),
      },
      {
        key: "status",
        header: t("assessment.approvals.status"),
        render: (row) => (
          <Badge variant={STATUS_VARIANT[row.status]}>
            {t(`assessment.dashboard.status.${row.status}`)}
          </Badge>
        ),
      },
      {
        key: "submitted",
        header: t("assessment.approvals.submitted_at"),
        render: (row) => shortDate(row.submitted_at),
      },
      {
        key: "actions",
        header: "",
        render: (row) => (
          <Button
            variant="outline"
            size="sm"
            data-testid={`approval-review-${row.section_code}-${row.subject_id}`}
            onClick={() => {
              setNotice(null);
              setError(null);
              setComment("");
              setSelected(row);
            }}
          >
            {t("assessment.approvals.review")}
          </Button>
        ),
      },
    ],
    [t],
  );

  const actionable =
    selected !== null &&
    ((selected.status === "submitted" && canApprove) ||
      (selected.status === "approved" && canPublish));

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("assessment.approvals.title")}</CardTitle>
          <CardDescription>{t("assessment.approvals.intro")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <Field label={t("assessment.dashboard.year")}>
              <Select
                data-testid="approval-year"
                value={yearId}
                onChange={(event) => {
                  setYearId(event.target.value);
                  setTermId("");
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
                data-testid="approval-term"
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
            <Field label={t("assessment.approvals.status")}>
              <Select
                data-testid="approval-status"
                value={status}
                onChange={(event) =>
                  setStatus(event.target.value as StatusFilter)
                }
              >
                {STATUSES.map((item) => (
                  <option key={item} value={item}>
                    {item === "all"
                      ? t("assessment.approvals.all")
                      : t(`assessment.dashboard.status.${item}`)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {notice ? (
            <p
              role="status"
              className="mt-4 text-sm text-muted-foreground"
              data-testid="approval-notice"
            >
              {notice}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {years.isLoading ? (
        <LoadingState label={t("assessment.approvals.title")} />
      ) : null}

      {submissions.isError && !submissions.data ? (
        <ErrorState
          title={t("assessment.approvals.load_error")}
          retry={
            <Button
              variant="outline"
              onClick={() => void submissions.refetch()}
            >
              {t("common.retry")}
            </Button>
          }
        />
      ) : null}

      {submissions.data ? (
        <DataTable
          columns={columns}
          rows={submissions.data.items}
          rowKey={(row) => row.id}
          caption={t("assessment.approvals.title")}
          emptyTitle={t("assessment.approvals.empty")}
          emptyDescription={t("assessment.approvals.empty_hint")}
        />
      ) : null}

      <Dialog
        open={selected !== null}
        onClose={closeReview}
        title={t("assessment.approvals.review_title")}
        description={
          selected
            ? `${selected.section_code} · ${selected.subject_name}`
            : undefined
        }
        closeLabel={t("assessment.approvals.close")}
        wide
        footer={
          <>
            <Button variant="outline" onClick={closeReview}>
              {t("assessment.approvals.close")}
            </Button>
            {selected?.status === "submitted" && canApprove ? (
              <>
                <Button
                  variant="destructive"
                  data-testid="approval-reject"
                  disabled={!comment.trim() || transition.isPending}
                  onClick={() => {
                    setError(null);
                    transition.mutate("reject");
                  }}
                >
                  {t("assessment.approvals.reject")}
                </Button>
                <Button
                  data-testid="approval-approve"
                  disabled={transition.isPending}
                  onClick={() => {
                    setError(null);
                    transition.mutate("approve");
                  }}
                >
                  {t("assessment.approvals.approve")}
                </Button>
              </>
            ) : null}
            {selected?.status === "approved" && canPublish ? (
              <Button
                data-testid="approval-publish"
                disabled={transition.isPending}
                onClick={() => {
                  setError(null);
                  transition.mutate("publish");
                }}
              >
                {t("assessment.approvals.publish")}
              </Button>
            ) : null}
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <p className="ui-help">{t("assessment.approvals.review_hint")}</p>
          {assessments.isLoading || sheets.isLoading ? (
            <LoadingState label={t("assessment.approvals.review_title")} />
          ) : null}
          {assessments.data && assessmentItems.length === 0 ? (
            <p className="ui-help" data-testid="approval-no-assessments">
              {t("assessment.approvals.no_assessments")}
            </p>
          ) : null}
          <ul className="flex flex-col gap-2" data-testid="approval-sheets">
            {sheets.data?.map((sheet) => (
              <li
                key={sheet.assessment_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded border p-3"
              >
                <span className="font-medium">{sheet.title}</span>
                <span className="ui-help">
                  {t("assessment.approvals.entered", {
                    entered: sheet.stats.entered,
                    total: sheet.stats.total,
                  })}
                </span>
                <span className="ui-num">
                  {sheet.stats.average_percent === null
                    ? "—"
                    : t("assessment.approvals.average", {
                        average: sheet.stats.average_percent,
                      })}
                </span>
              </li>
            ))}
          </ul>
          {actionable ? (
            <Field
              label={t("assessment.approvals.comment")}
              hint={t("assessment.approvals.comment_hint")}
            >
              <Textarea
                data-testid="approval-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
              />
            </Field>
          ) : null}
          {selected?.status === "submitted" && canApprove && !comment.trim() ? (
            <p className="ui-help" data-testid="approval-comment-required">
              {t("assessment.approvals.comment_required")}
            </p>
          ) : null}
          {error ? (
            <p
              role="alert"
              className="text-sm text-destructive"
              data-testid="approval-error"
            >
              {error}
            </p>
          ) : null}
          {!actionable && selected ? (
            <p className="ui-help" data-testid="approval-readonly">
              {t(`assessment.dashboard.status.${selected.status}`)}
            </p>
          ) : null}
        </div>
      </Dialog>
    </div>
  );
}
