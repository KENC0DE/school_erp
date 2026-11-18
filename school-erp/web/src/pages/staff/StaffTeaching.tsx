import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Select,
} from "@erp/ui-web";
import { useState, type FormEvent } from "react";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import {
  useSubjects,
  useSections,
  useYears,
} from "../academics/queries";
import { STAFF, useTeachingAssignments } from "./queries";
import type { TeachingAssignment } from "./types";

interface AssignmentForm {
  year_id: string;
  section_id: string;
  subject_id: string;
  notes: string;
}

const EMPTY_FORM: AssignmentForm = {
  year_id: "",
  section_id: "",
  subject_id: "",
  notes: "",
};

export function StaffTeaching({
  staffId,
  canManage,
}: {
  staffId: string;
  canManage: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const assignments = useTeachingAssignments(staffId);
  const years = useYears();
  const subjects = useSubjects();
  const [form, setForm] = useState<AssignmentForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sections = useSections(form?.year_id || null);

  const save = useMutation({
    mutationFn: (data: AssignmentForm) =>
      api.post<TeachingAssignment>(`${STAFF}/${staffId}/teaching-assignments`, {
        year_id: data.year_id,
        section_id: data.section_id,
        subject_id: data.subject_id,
        notes: data.notes.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "teaching", staffId] });
      setForm(null);
    },
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("staff.teaching.failed"));
    },
  });

  const remove = useMutation({
    mutationFn: (assignmentId: string) =>
      api.del(`${STAFF}/${staffId}/teaching-assignments/${assignmentId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "teaching", staffId] });
    },
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("staff.teaching.failed"));
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setError(null);
    save.mutate(form);
  }

  if (assignments.isPending) {
    return <LoadingState label={t("common.loading")} testId="teaching-loading" />;
  }
  if (assignments.isError) {
    return (
      <ErrorState
        title={t("staff.load_error")}
        requestId={requestIdOf(assignments.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button variant="outline" onClick={() => void assignments.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  const rows = assignments.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="staff-teaching">
      {canManage ? (
        <Button
          onClick={() => {
            setError(null);
            setForm({ ...EMPTY_FORM });
          }}
        >
          {t("staff.teaching.add")}
        </Button>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState title={t("staff.teaching.empty")} />
      ) : (
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t("staff.teaching.title")}>
          <table className="ui-table" data-testid="teaching-table">
            <thead>
              <tr>
                <th scope="col">{t("staff.teaching.year")}</th>
                <th scope="col">{t("staff.teaching.level")}</th>
                <th scope="col">{t("staff.teaching.section")}</th>
                <th scope="col">{t("staff.teaching.subject")}</th>
                <th scope="col">{t("staff.common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((assignment) => (
                <tr key={assignment.id} data-testid={`teaching-row-${assignment.id}`}>
                  <td>{assignment.year_code}</td>
                  <td>{assignment.level_name}</td>
                  <td>{assignment.section_code}</td>
                  <td>{assignment.subject_name}</td>
                  <td>
                    {canManage ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={remove.isPending}
                        onClick={() => remove.mutate(assignment.id)}
                      >
                        {t("staff.teaching.delete")}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <Dialog
        open={form !== null}
        onClose={() => setForm(null)}
        title={t("staff.teaching.add")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              form="teaching-form"
              disabled={!form?.year_id || !form.section_id || !form.subject_id || save.isPending}
            >
              {save.isPending ? t("staff.teaching.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        {form ? (
          <form id="teaching-form" className="space-y-3" onSubmit={submit}>
            <Field label={t("staff.teaching.year")}>
              <Select
                required
                value={form.year_id}
                onChange={(event) =>
                  setForm({ ...form, year_id: event.target.value, section_id: "" })
                }
              >
                <option value="">{t("staff.not_set")}</option>
                {(years.data?.items ?? []).map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.teaching.section")}>
              <Select
                required
                value={form.section_id}
                disabled={!form.year_id}
                onChange={(event) => setForm({ ...form, section_id: event.target.value })}
              >
                <option value="">{t("staff.not_set")}</option>
                {(sections.data?.items ?? []).map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.code}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.teaching.subject")}>
              <Select
                required
                value={form.subject_id}
                onChange={(event) => setForm({ ...form, subject_id: event.target.value })}
              >
                <option value="">{t("staff.not_set")}</option>
                {(subjects.data?.items ?? []).map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.teaching.notes")}>
              <Input
                value={form.notes}
                onChange={(event) => setForm({ ...form, notes: event.target.value })}
              />
            </Field>
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
          </form>
        ) : null}
      </Dialog>
    </div>
  );
}
