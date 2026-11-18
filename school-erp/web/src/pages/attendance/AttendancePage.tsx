import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardContent,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Page,
  PageHeader,
  Textarea,
} from "@erp/ui-web";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import {
  useLevels,
  useSections,
  useYears,
} from "../students/queries";
import { ATTENDANCE, useSessionDetail, useSessions } from "./queries";
import {
  EMPTY_FILTERS,
  RECORD_STATUSES,
  SESSION_STATUSES,
  changedRecords,
  draftsFrom,
  todayIso,
  type AttendanceRecord,
  type RecordDraft,
  type RecordInput,
  type RecordStatus,
  type SessionCounts,
  type SessionDetail,
  type SessionFilters,
  type SessionStatus,
} from "./types";

const BULK_LIMIT = 200;

function statusVariant(
  status: SessionStatus,
): "neutral" | "success" | "warning" | "danger" {
  if (status === "open") return "success";
  if (status === "submitted") return "warning";
  return "neutral";
}

function countsFromDrafts(
  detail: SessionDetail,
  drafts: Record<string, RecordDraft>,
): SessionCounts {
  const counts: SessionCounts = {
    total: detail.roster.length,
    present: 0,
    absent: 0,
    late: 0,
    excused: 0,
  };
  for (const entry of detail.roster) {
    const status = drafts[entry.student_id]?.status;
    if (status) counts[status] += 1;
  }
  return counts;
}

function recordFor(
  detail: SessionDetail,
  studentId: string,
): AttendanceRecord | undefined {
  return detail.records.find((record) => record.student_id === studentId);
}

export function AttendancePage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const permissions = user?.permissions ?? [];
  const canView =
    permissions.includes("*") || permissions.includes("attendance.view");
  const canRecord =
    permissions.includes("*") || permissions.includes("attendance.record");
  const canManage =
    permissions.includes("*") || permissions.includes("attendance.manage");

  const [filters, setFilters] = useState<SessionFilters>({ ...EMPTY_FILTERS });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, RecordDraft>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createYear, setCreateYear] = useState("");
  const [createLevel, setCreateLevel] = useState("");
  const [createSection, setCreateSection] = useState("");
  const [createDate, setCreateDate] = useState(todayIso());
  const [createPeriod, setCreatePeriod] = useState("");
  const [createNotes, setCreateNotes] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const years = useYears();
  const levels = useLevels();
  const sections = useSections(filters.year_id, filters.level_id);
  const createSections = useSections(createYear, createLevel);
  const sessions = useSessions(filters);
  const detail = useSessionDetail(selectedId);

  useEffect(() => {
    if (!filters.year_id && years.data) {
      const yearId = years.data.current_year_id ?? years.data.items[0]?.id ?? "";
      if (yearId) {
        setFilters((current) => ({ ...current, year_id: yearId }));
        setCreateYear((current) => current || yearId);
      }
    }
  }, [filters.year_id, years.data]);

  useEffect(() => {
    if (!filters.level_id && levels.data?.items.length) {
      const levelId = levels.data.items[0].id;
      setFilters((current) => ({ ...current, level_id: levelId }));
      setCreateLevel((current) => current || levelId);
    }
  }, [filters.level_id, levels.data]);

  useEffect(() => {
    const items = createSections.data?.items ?? [];
    if (items.length === 0) return;
    if (!items.some((section) => section.id === createSection)) {
      setCreateSection(items[0].id);
    }
  }, [createSection, createSections.data]);

  useEffect(() => {
    if (!detail.data) return;
    setDrafts(draftsFrom(detail.data));
    setError(null);
  }, [detail.data]);

  const filteredSessions = useMemo(() => {
    const items = sessions.data?.items ?? [];
    if (!filters.section_id) return items;
    return items.filter((item) => item.section_id === filters.section_id);
  }, [filters.section_id, sessions.data]);

  const create = useMutation({
    mutationFn: () =>
      api.post<SessionDetail>(ATTENDANCE, {
        year_id: createYear,
        section_id: createSection,
        date: createDate,
        period: createPeriod.trim() ? Number(createPeriod) : undefined,
        notes: createNotes.trim() || null,
      }),
    onSuccess: (created) => {
      setCreateOpen(false);
      setCreateError(null);
      setCreateNotes("");
      setCreatePeriod("");
      setSelectedId(created.id);
      setMessage(t("attendance.session.created"));
      queryClient.setQueryData(["attendance", "session", created.id], created);
      void queryClient.invalidateQueries({ queryKey: ["attendance", "sessions"] });
    },
    onError: (caught) => {
      setCreateError(
        caught instanceof Error ? caught.message : t("attendance.session.create_failed"),
      );
    },
  });

  const save = useMutation({
    mutationFn: async (items: RecordInput[]) => {
      if (!selectedId) throw new Error("No register selected");
      let latest: SessionDetail | null = null;
      for (let index = 0; index < items.length; index += BULK_LIMIT) {
        latest = await api.post<SessionDetail>(
          `${ATTENDANCE}/${selectedId}/records`,
          { items: items.slice(index, index + BULK_LIMIT) },
        );
      }
      return latest;
    },
    onSuccess: (saved) => {
      if (!saved) return;
      setMessage(t("attendance.record.saved"));
      setError(null);
      queryClient.setQueryData(["attendance", "session", selectedId], saved);
      void queryClient.invalidateQueries({ queryKey: ["attendance", "sessions"] });
    },
    onError: (caught) => {
      setError(
        caught instanceof Error ? caught.message : t("attendance.record.save_failed"),
      );
    },
  });

  const transition = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "submit" | "lock" | "reopen" }) =>
      api.post<SessionDetail>(`${ATTENDANCE}/${id}/${action}`),
    onSuccess: (updated) => {
      setMessage(null);
      setError(null);
      queryClient.setQueryData(["attendance", "session", updated.id], updated);
      void queryClient.invalidateQueries({ queryKey: ["attendance", "sessions"] });
    },
    onError: (caught) => {
      setError(caught instanceof Error ? caught.message : t("common.error"));
    },
  });

  if (!canView) {
    return (
      <Page>
        <Card>
          <CardContent className="p-6">
            <EmptyState title={t("attendance.perm.view")} />
          </CardContent>
        </Card>
      </Page>
    );
  }

  function openCreate(): void {
    setCreateError(null);
    setCreateYear(filters.year_id || years.data?.current_year_id || "");
    setCreateLevel(filters.level_id || levels.data?.items[0]?.id || "");
    setCreateSection(filters.section_id || "");
    setCreateDate(filters.date || todayIso());
    setCreateOpen(true);
  }

  function updateDraft(studentId: string, patch: Partial<RecordDraft>): void {
    setDrafts((current) => ({
      ...current,
      [studentId]: { ...current[studentId], ...patch },
    }));
  }

  function markAllPresent(): void {
    setDrafts((current) => {
      const next: Record<string, RecordDraft> = {};
      for (const [studentId, draft] of Object.entries(current)) {
        next[studentId] = { ...draft, status: "present", reason: "", late_minutes: "" };
      }
      return next;
    });
  }

  function submitChanges(): void {
    if (!detail.data) return;
    const items = changedRecords(detail.data, drafts).map((item) => {
      const { student_id, status } = item;
      return item.reason || item.late_minutes !== null
        ? item
        : { student_id, status };
    });
    if (items.length === 0) {
      setMessage(t("attendance.record.no_changes"));
      return;
    }
    save.mutate(items);
  }

  const rows = filteredSessions;
  const selected = detail.data;
  const selectedCounts = selected ? countsFromDrafts(selected, drafts) : null;
  const pending = selected ? changedRecords(selected, drafts) : [];
  const editable = selected?.status === "open" && canRecord;

  return (
    <Page>
      <PageHeader title={t("attendance.title")} description={t("attendance.intro")} />

      <Card>
        <CardContent className="space-y-4 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-44 space-y-1 text-sm">
              <span className="font-medium">{t("attendance.session.year")}</span>
              <select
                className="ui-select"
                data-testid="attendance-year"
                value={filters.year_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    year_id: event.target.value,
                    section_id: "",
                  }))
                }
              >
                {(years.data?.items ?? []).map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="min-w-40 space-y-1 text-sm">
              <span className="font-medium">{t("attendance.session.level")}</span>
              <select
                className="ui-select"
                data-testid="attendance-level"
                value={filters.level_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    level_id: event.target.value,
                    section_id: "",
                  }))
                }
              >
                {(levels.data?.items ?? []).map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="min-w-40 space-y-1 text-sm">
              <span className="font-medium">{t("attendance.session.section")}</span>
              <select
                className="ui-select"
                data-testid="attendance-section"
                value={filters.section_id}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, section_id: event.target.value }))
                }
              >
                <option value="">{t("attendance.session.filter_section")}</option>
                {(sections.data?.items ?? []).map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.name ?? section.code}
                  </option>
                ))}
              </select>
            </label>

            <label className="min-w-40 space-y-1 text-sm">
              <span className="font-medium">{t("attendance.session.date")}</span>
              <Input
                type="date"
                data-testid="attendance-date"
                value={filters.date}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, date: event.target.value }))
                }
              />
            </label>

            <label className="min-w-40 space-y-1 text-sm">
              <span className="font-medium">{t("attendance.session.status")}</span>
              <select
                className="ui-select"
                data-testid="attendance-status"
                value={filters.status}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    status: event.target.value as SessionFilters["status"],
                  }))
                }
              >
                <option value="">{t("attendance.session.all_statuses")}</option>
                {SESSION_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {t(`attendance.status.${status}`)}
                  </option>
                ))}
              </select>
            </label>

            {canRecord ? (
              <Button
                data-testid="attendance-open"
                onClick={openCreate}
                disabled={!filters.year_id}
              >
                {t("attendance.session.open")}
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {message ? (
        <p role="status" className="text-sm text-primary" data-testid="attendance-message">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-destructive" data-testid="attendance-error">
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card>
          <CardContent className="p-4">
            {sessions.isPending ? (
              <LoadingState label={t("attendance.session.loading")} testId="attendance-loading" />
            ) : sessions.isError ? (
              <ErrorState
                title={t("attendance.session.load_error")}
                requestId={requestIdOf(sessions.error)}
                requestIdLabel={t("common.request_id")}
                retry={
                  <Button variant="outline" onClick={() => void sessions.refetch()}>
                    {t("common.retry")}
                  </Button>
                }
                testId="attendance-list-error"
              />
            ) : rows.length === 0 ? (
              <EmptyState
                title={t("attendance.session.empty")}
                description={t("attendance.session.empty_hint")}
                testId="attendance-empty"
              />
            ) : (
              <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t("attendance.session.title")}>
                <table className="ui-table" data-testid="attendance-table">
                  <caption className="ui-visually-hidden">{t("attendance.session.title")}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{t("attendance.session.date")}</th>
                      <th scope="col">{t("attendance.session.section")}</th>
                      <th scope="col">{t("attendance.session.status")}</th>
                      <th scope="col">{t("attendance.record.status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((item) => (
                      <tr key={item.id} data-testid={`attendance-row-${item.id}`}>
                        <td>
                          <button
                            type="button"
                            className="ui-link"
                            onClick={() => setSelectedId(item.id)}
                          >
                            {item.date}
                          </button>
                        </td>
                        <td>
                          {item.level_name} · {item.section_name ?? item.section_code}
                          {item.period ? (
                            <span className="block text-xs text-muted-foreground">
                              {t("attendance.session.period")} {item.period}
                            </span>
                          ) : null}
                        </td>
                        <td>
                          <Badge variant={statusVariant(item.status)}>
                            {t(`attendance.status.${item.status}`)}
                          </Badge>
                        </td>
                        <td>
                          {t("attendance.count.present", { count: item.counts.present })} ·{" "}
                          {t("attendance.count.absent", { count: item.counts.absent })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="border-t border-border px-1 py-2 text-xs text-muted-foreground">
                  {t("attendance.session.count", {
                    count: sessions.data?.total ?? rows.length,
                  })}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 p-4">
            {!selectedId ? (
              <EmptyState title={t("attendance.record.roster")} description={t("attendance.record.default_present")} />
            ) : detail.isPending ? (
              <LoadingState label={t("attendance.session.loading")} testId="attendance-detail-loading" />
            ) : detail.isError || !selected ? (
              <ErrorState
                title={t("attendance.session.not_found")}
                requestId={requestIdOf(detail.error)}
                requestIdLabel={t("common.request_id")}
                retry={
                  <Button variant="outline" onClick={() => void detail.refetch()}>
                    {t("common.retry")}
                  </Button>
                }
                testId="attendance-detail-error"
              />
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold">
                      {selected.date} · {selected.level_name} ·{" "}
                      {selected.section_name ?? selected.section_code}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {t(`attendance.mode.${selected.mode}`)}
                      {selected.period
                        ? ` · ${t("attendance.session.period")} ${selected.period}`
                        : ""}
                    </p>
                  </div>
                  <Badge variant={statusVariant(selected.status)}>
                    {t(`attendance.status.${selected.status}`)}
                  </Badge>
                </div>

                {selectedCounts ? (
                  <p className="text-sm text-muted-foreground" data-testid="attendance-counts">
                    {t("attendance.count.total", { count: selectedCounts.total })} ·{" "}
                    {t("attendance.count.present", { count: selectedCounts.present })} ·{" "}
                    {t("attendance.count.absent", { count: selectedCounts.absent })} ·{" "}
                    {t("attendance.count.late", { count: selectedCounts.late })} ·{" "}
                    {t("attendance.count.excused", { count: selectedCounts.excused })}
                  </p>
                ) : null}

                {selected.status !== "open" ? (
                  <p role="note" className="text-sm text-muted-foreground" data-testid="attendance-closed">
                    {t("attendance.session.closed")}
                  </p>
                ) : null}

                {selected.roster.length === 0 ? (
                  <EmptyState title={t("attendance.record.empty")} />
                ) : (
                  <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t("attendance.record.roster")}>
                    <table className="ui-table" data-testid="attendance-roster">
                      <caption className="ui-visually-hidden">{t("attendance.record.roster")}</caption>
                      <thead>
                        <tr>
                          <th scope="col">{t("attendance.record.roll_number")}</th>
                          <th scope="col">{t("attendance.record.student")}</th>
                          <th scope="col">{t("attendance.record.status")}</th>
                          <th scope="col">{t("attendance.record.reason")}</th>
                          <th scope="col">{t("attendance.record.late_minutes")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selected.roster.map((entry) => {
                          const draft = drafts[entry.student_id];
                          const record = recordFor(selected, entry.student_id);
                          return (
                            <tr key={entry.student_id} data-testid={`attendance-student-${entry.student_id}`}>
                              <td className="ui-num">{entry.roll_number ?? "—"}</td>
                              <td>
                                {entry.full_name}
                                {record?.student_name_am ? (
                                  <span className="block text-xs text-muted-foreground" lang="am" dir="auto">
                                    {record.student_name_am}
                                  </span>
                                ) : null}
                              </td>
                              <td>
                                <select
                                  className="ui-select"
                                  aria-label={`${entry.full_name} ${t("attendance.record.status")}`}
                                  data-testid={`attendance-status-${entry.student_id}`}
                                  value={draft?.status ?? "present"}
                                  disabled={!editable}
                                  onChange={(event) =>
                                    updateDraft(entry.student_id, {
                                      status: event.target.value as RecordStatus,
                                      reason:
                                        event.target.value === "present" ? "" : draft?.reason ?? "",
                                      late_minutes:
                                        event.target.value === "late"
                                          ? draft?.late_minutes ?? ""
                                          : "",
                                    })
                                  }
                                >
                                  {RECORD_STATUSES.map((status) => (
                                    <option key={status} value={status}>
                                      {t(`attendance.record.${status}`)}
                                    </option>
                                  ))}
                                </select>
                              </td>
                              <td>
                                <Input
                                  aria-label={`${entry.full_name} ${t("attendance.record.reason")}`}
                                  data-testid={`attendance-reason-${entry.student_id}`}
                                  value={draft?.reason ?? ""}
                                  disabled={!editable || draft?.status === "present"}
                                  onChange={(event) =>
                                    updateDraft(entry.student_id, { reason: event.target.value })
                                  }
                                />
                              </td>
                              <td>
                                <Input
                                  type="number"
                                  min={0}
                                  max={600}
                                  aria-label={`${entry.full_name} ${t("attendance.record.late_minutes")}`}
                                  data-testid={`attendance-late-${entry.student_id}`}
                                  value={draft?.late_minutes ?? ""}
                                  disabled={!editable || draft?.status !== "late"}
                                  onChange={(event) =>
                                    updateDraft(entry.student_id, {
                                      late_minutes: event.target.value,
                                    })
                                  }
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  {editable ? (
                    <>
                      <Button
                        data-testid="attendance-save"
                        onClick={submitChanges}
                        loading={save.isPending}
                        disabled={pending.length === 0}
                      >
                        {save.isPending
                          ? t("attendance.record.saving")
                          : t("attendance.record.save")}
                      </Button>
                      <Button variant="outline" data-testid="attendance-all-present" onClick={markAllPresent}>
                        {t("attendance.record.mark_all_present")}
                      </Button>
                      <Button
                        variant="outline"
                        data-testid="attendance-submit"
                        loading={transition.isPending}
                        onClick={() =>
                          transition.mutate({ id: selected.id, action: "submit" })
                        }
                      >
                        {t("attendance.session.submit")}
                      </Button>
                    </>
                  ) : null}
                  {canManage && selected.status !== "locked" ? (
                    <Button
                      variant="outline"
                      data-testid="attendance-lock"
                      loading={transition.isPending}
                      onClick={() => transition.mutate({ id: selected.id, action: "lock" })}
                    >
                      {t("attendance.session.lock")}
                    </Button>
                  ) : null}
                  {canManage && selected.status === "locked" ? (
                    <Button
                      variant="outline"
                      data-testid="attendance-reopen"
                      loading={transition.isPending}
                      onClick={() => transition.mutate({ id: selected.id, action: "reopen" })}
                    >
                      {t("attendance.session.reopen")}
                    </Button>
                  ) : null}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title={t("attendance.session.open_title")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              data-testid="attendance-create-save"
              loading={create.isPending}
              disabled={!createYear || !createSection || !createDate}
              onClick={() => create.mutate()}
            >
              {create.isPending ? t("attendance.session.opening") : t("attendance.session.open")}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("attendance.session.year")}>
              <select
                className="ui-select"
                data-testid="attendance-create-year"
                value={createYear}
                onChange={(event) => {
                  setCreateYear(event.target.value);
                  setCreateSection("");
                }}
              >
                {(years.data?.items ?? []).map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("attendance.session.level")}>
              <select
                className="ui-select"
                data-testid="attendance-create-level"
                value={createLevel}
                onChange={(event) => {
                  setCreateLevel(event.target.value);
                  setCreateSection("");
                }}
              >
                {(levels.data?.items ?? []).map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("attendance.session.section")}>
              <select
                className="ui-select"
                data-testid="attendance-create-section"
                value={createSection}
                onChange={(event) => setCreateSection(event.target.value)}
              >
                <option value="">{t("attendance.session.filter_section")}</option>
                {(createSections.data?.items ?? []).map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.name ?? section.code}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("attendance.session.date")}>
              <Input
                type="date"
                data-testid="attendance-create-date"
                value={createDate}
                onChange={(event) => setCreateDate(event.target.value)}
              />
            </Field>
            <Field label={t("attendance.session.period")}>
              <Input
                type="number"
                min={1}
                max={20}
                data-testid="attendance-create-period"
                value={createPeriod}
                onChange={(event) => setCreatePeriod(event.target.value)}
              />
            </Field>
          </div>
          <Field label={t("attendance.session.notes")}>
            <Textarea
              data-testid="attendance-create-notes"
              value={createNotes}
              onChange={(event) => setCreateNotes(event.target.value)}
            />
          </Field>
          {createError ? (
            <p role="alert" className="text-sm text-destructive" data-testid="attendance-create-error">
              {createError}
            </p>
          ) : null}
        </div>
      </Dialog>
    </Page>
  );
}
