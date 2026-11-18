import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Page,
  PageHeader,
  Select,
} from "@erp/ui-web";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Card, CardContent } from "../../components/ui/Card";
import { requestIdOf } from "../../lib/errors";
import { api } from "../../lib/api";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { hasPermission, useLevels, useSections, useYears } from "./queries";
import type {
  PromotionAction,
  PromotionApplyOut,
  PromotionExceptionInput,
  PromotionPreview,
  PromotionRequestInput,
  PromotionRow,
} from "./types";

const PROMOTIONS = "/api/v1/students/promotions";
const ACTIONS: PromotionAction[] = ["promote", "repeat", "graduate", "skip"];

function targetLabel(row: PromotionRow, t: (key: string) => string): string {
  if (row.action === "skip") return t("students.progress.none");
  const level = row.target_level_name ?? t("students.progress.none");
  if (row.action === "graduate") return level;
  const section =
    row.target_section_code ?? t("students.progress.auto_section");
  return `${level} · ${section}`;
}

export function PromotionPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const canManage = hasPermission(user?.permissions, "students.manage");

  const [sourceYearId, setSourceYearId] = useState("");
  const [targetYearId, setTargetYearId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [reason, setReason] = useState("");
  const [overrides, setOverrides] = useState<Record<string, PromotionAction>>(
    {},
  );
  const [applied, setApplied] = useState<PromotionApplyOut | null>(null);

  const years = useYears();
  const levels = useLevels();
  const sections = useSections(sourceYearId, levelId);
  const yearItems = years.data?.items ?? [];

  const sourceId = useMemo(() => {
    if (sourceYearId && yearItems.some((item) => item.id === sourceYearId))
      return sourceYearId;
    return years.data?.current_year_id ?? yearItems[0]?.id ?? "";
  }, [sourceYearId, yearItems, years.data?.current_year_id]);

  const targetId = useMemo(() => {
    if (targetYearId && yearItems.some((item) => item.id === targetYearId))
      return targetYearId;
    const index = yearItems.findIndex((item) => item.id === sourceId);
    if (index < 0) return "";
    // The API returns newest first, so the previous entry is the next year.
    return yearItems[index - 1]?.id ?? "";
  }, [targetYearId, yearItems, sourceId]);

  function requestFor(
    chosen: Record<string, PromotionAction> = overrides,
  ): PromotionRequestInput {
    const exceptions: PromotionExceptionInput[] = Object.entries(chosen).map(
      ([studentId, action]) => ({ student_id: studentId, action }),
    );
    return {
      source_year_id: sourceId,
      target_year_id: targetId,
      ...(levelId ? { source_level_id: levelId } : {}),
      ...(sectionId ? { source_section_id: sectionId } : {}),
      ...(exceptions.length ? { exceptions } : {}),
    };
  }

  const preview = useMutation({
    mutationFn: (body: PromotionRequestInput) =>
      api.post<PromotionPreview>(`${PROMOTIONS}/preview`, body),
    onSuccess: () => setApplied(null),
  });

  const apply = useMutation({
    mutationFn: (body: PromotionRequestInput) =>
      api.post<PromotionApplyOut>(`${PROMOTIONS}/apply`, {
        ...body,
        ...(reason.trim() ? { reason: reason.trim() } : {}),
      }),
    onSuccess: (result) => {
      setApplied(result);
      setOverrides({});
      preview.reset();
      void queryClient.invalidateQueries({ queryKey: ["students"] });
    },
  });

  function changeAction(row: PromotionRow, action: PromotionAction) {
    const next = { ...overrides, [row.student_id]: action };
    setOverrides(next);
    preview.mutate(requestFor(next));
  }

  if (!canManage) {
    return (
      <Page>
        <Card>
          <CardContent className="p-6">
            <EmptyState
              title={t("students.progress.permission_denied")}
              testId="promotion-denied"
            />
          </CardContent>
        </Card>
      </Page>
    );
  }

  const data = preview.data;
  const ready = Boolean(sourceId && targetId && sourceId !== targetId);
  const previewError = preview.error;
  const applyError = apply.error;

  return (
    <Page>
      <PageHeader
        breadcrumbs={
          <Link className="ui-link text-sm" to="/students">
            {t("students.back_to_list")}
          </Link>
        }
        title={t("students.progress.title")}
        description={t("students.progress.intro")}
      />

      <Card>
        <CardContent className="space-y-4 p-4" data-testid="promotion-filters">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label={t("students.progress.source_year")}>
              <Select
                data-testid="promotion-source-year"
                value={sourceId}
                onChange={(event) => {
                  setSourceYearId(event.target.value);
                  setTargetYearId("");
                  setSectionId("");
                  setOverrides({});
                  preview.reset();
                  setApplied(null);
                }}
              >
                {yearItems.map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("students.progress.target_year")}>
              <Select
                data-testid="promotion-target-year"
                value={targetId}
                onChange={(event) => {
                  setTargetYearId(event.target.value);
                  setOverrides({});
                  preview.reset();
                  setApplied(null);
                }}
              >
                {yearItems.map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("students.progress.level")}>
              <Select
                data-testid="promotion-level"
                value={levelId}
                onChange={(event) => {
                  setLevelId(event.target.value);
                  setSectionId("");
                  setOverrides({});
                  preview.reset();
                }}
              >
                <option value="">{t("students.progress.all_levels")}</option>
                {(levels.data?.items ?? []).map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("students.progress.section")}>
              <Select
                data-testid="promotion-section"
                value={sectionId}
                disabled={!sourceId || !levelId}
                onChange={(event) => {
                  setSectionId(event.target.value);
                  setOverrides({});
                  preview.reset();
                }}
              >
                <option value="">{t("students.progress.all_sections")}</option>
                {(sections.data?.items ?? []).map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.code}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field
            label={t("students.progress.reason")}
            hint={t("students.progress.reason_hint")}
          >
            <Input
              data-testid="promotion-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </Field>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              data-testid="promotion-preview"
              disabled={!ready || preview.isPending}
              onClick={() => {
                setOverrides({});
                preview.mutate(requestFor({}));
              }}
            >
              {preview.isPending
                ? t("students.progress.previewing")
                : t("students.progress.preview")}
            </Button>
            {!ready ? (
              <span className="text-xs text-muted-foreground">
                {t("students.progress.select_years")}
              </span>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {applied ? (
        <Card>
          <CardContent className="p-4">
            <p
              className="text-sm text-primary"
              role="status"
              data-testid="promotion-applied"
            >
              {t("students.progress.applied", {
                promoted: applied.promoted,
                repeated: applied.repeated,
                graduated: applied.graduated,
                skipped: applied.skipped,
              })}
            </p>
          </CardContent>
        </Card>
      ) : null}

      {applyError ? (
        <p
          className="text-sm text-destructive"
          role="alert"
          data-testid="promotion-apply-error"
        >
          {applyError instanceof ApiRequestError
            ? applyError.message
            : t("students.progress.apply_error")}
        </p>
      ) : null}

      {preview.isPending ? (
        <LoadingState
          label={t("students.progress.loading")}
          testId="promotion-preview-loading"
        />
      ) : previewError ? (
        <Card>
          <CardContent className="p-6">
            <ErrorState
              title={t("students.progress.load_error")}
              requestId={requestIdOf(previewError)}
              requestIdLabel={t("common.request_id")}
              retry={
                ready ? (
                  <Button
                    variant="outline"
                    onClick={() => preview.mutate(requestFor())}
                  >
                    {t("common.retry")}
                  </Button>
                ) : undefined
              }
              testId="promotion-preview-error"
            />
          </CardContent>
        </Card>
      ) : data ? (
        data.items.length === 0 ? (
          <Card>
            <CardContent className="p-6">
              <EmptyState
                title={t("students.progress.empty")}
                description={t("students.progress.empty_hint")}
                testId="promotion-preview-empty"
              />
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="space-y-3 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm" data-testid="promotion-summary">
                  {t("students.progress.summary", {
                    total: data.total,
                    promote: data.promote,
                    repeat: data.repeat,
                    graduate: data.graduate,
                    skip: data.skip,
                  })}
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  {data.blocking > 0 ? (
                    <p className="text-sm text-destructive" role="alert">
                      {t("students.progress.blocking_count", {
                        count: data.blocking,
                      })}
                    </p>
                  ) : null}
                  <Button
                    data-testid="promotion-apply"
                    disabled={apply.isPending || data.blocking > 0}
                    onClick={() => apply.mutate(requestFor())}
                  >
                    {apply.isPending
                      ? t("students.progress.applying")
                      : t("students.progress.apply")}
                  </Button>
                </div>
              </div>

              <div
                className="overflow-x-auto"
                tabIndex={0}
                role="region"
                aria-label={t("students.progress.title")}
              >
                <table className="ui-table" data-testid="promotion-table">
                  <thead>
                    <tr>
                      <th scope="col">
                        {t("students.progress.column.student")}
                      </th>
                      <th scope="col">
                        {t("students.progress.column.current")}
                      </th>
                      <th scope="col">
                        {t("students.progress.column.action")}
                      </th>
                      <th scope="col">
                        {t("students.progress.column.target")}
                      </th>
                      <th scope="col">
                        {t("students.progress.column.warnings")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((row) => (
                      <tr
                        key={row.student_id}
                        data-testid={`promotion-row-${row.student_id}`}
                        aria-invalid={row.blocking || undefined}
                      >
                        <td>
                          <span className="block font-medium">
                            {row.full_name}
                          </span>
                          <span className="ui-num block text-xs text-muted-foreground">
                            {row.student_number}
                          </span>
                        </td>
                        <td>
                          {[
                            row.current_level_name,
                            row.current_section_code ??
                              t("students.progress.none"),
                          ].join(" · ")}
                        </td>
                        <td>
                          <Select
                            aria-label={`${t("students.progress.column.action")} — ${row.full_name}`}
                            data-testid={`promotion-action-${row.student_id}`}
                            value={overrides[row.student_id] ?? row.action}
                            onChange={(event) =>
                              changeAction(
                                row,
                                event.target.value as PromotionAction,
                              )
                            }
                          >
                            {ACTIONS.map((action) => (
                              <option key={action} value={action}>
                                {t(`students.progress.action.${action}`)}
                              </option>
                            ))}
                          </Select>
                        </td>
                        <td>{targetLabel(row, t)}</td>
                        <td>
                          {row.warnings.length === 0 ? (
                            <span className="text-muted-foreground">
                              {t("students.progress.none")}
                            </span>
                          ) : (
                            <ul className="space-y-1 text-xs">
                              {row.warnings.map((warning) => (
                                <li
                                  key={warning}
                                  className={
                                    row.blocking
                                      ? "text-destructive"
                                      : "text-muted-foreground"
                                  }
                                >
                                  {t(warning)}
                                </li>
                              ))}
                            </ul>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )
      ) : null}
    </Page>
  );
}
