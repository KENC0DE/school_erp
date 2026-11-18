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
  Textarea,
} from "@erp/ui-web";
import { useState, type FormEvent } from "react";

import { CalendarDatePicker } from "../../components/CalendarDatePicker";
import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { STAFF, useQualifications } from "./queries";
import { QUALIFICATION_KINDS, type Qualification, type QualificationKind } from "./types";

interface QualificationForm {
  id: string | null;
  kind: QualificationKind;
  title: string;
  institution: string;
  field_of_study: string;
  start_date: string;
  end_date: string;
  result: string;
  notes: string;
  row_version: number;
}

const EMPTY_FORM: QualificationForm = {
  id: null,
  kind: "education",
  title: "",
  institution: "",
  field_of_study: "",
  start_date: "",
  end_date: "",
  result: "",
  notes: "",
  row_version: 0,
};

function formOf(qualification: Qualification): QualificationForm {
  return {
    id: qualification.id,
    kind: qualification.kind,
    title: qualification.title,
    institution: qualification.institution ?? "",
    field_of_study: qualification.field_of_study ?? "",
    start_date: qualification.start_date ?? "",
    end_date: qualification.end_date ?? "",
    result: qualification.result ?? "",
    notes: qualification.notes ?? "",
    row_version: qualification.row_version,
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function StaffQualifications({
  staffId,
  canManage,
}: {
  staffId: string;
  canManage: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const qualifications = useQualifications(staffId);
  const [form, setForm] = useState<QualificationForm | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (data: QualificationForm) => {
      const body = {
        kind: data.kind,
        title: data.title.trim(),
        institution: clean(data.institution),
        field_of_study: clean(data.field_of_study),
        start_date: clean(data.start_date),
        end_date: clean(data.end_date),
        result: clean(data.result),
        notes: clean(data.notes),
      };
      return data.id
        ? api.patch<Qualification>(`${STAFF}/${staffId}/qualifications/${data.id}`, {
            ...body,
            row_version: data.row_version,
          })
        : api.post<Qualification>(`${STAFF}/${staffId}/qualifications`, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "qualifications", staffId] });
      void queryClient.invalidateQueries({ queryKey: ["staff", "detail", staffId] });
      setForm(null);
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.qualification.failed"),
      );
    },
  });

  const remove = useMutation({
    mutationFn: (qualificationId: string) =>
      api.del(`${STAFF}/${staffId}/qualifications/${qualificationId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "qualifications", staffId] });
      void queryClient.invalidateQueries({ queryKey: ["staff", "detail", staffId] });
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.qualification.failed"),
      );
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setError(null);
    save.mutate(form);
  }

  if (qualifications.isPending) {
    return <LoadingState label={t("common.loading")} testId="qualifications-loading" />;
  }
  if (qualifications.isError) {
    return (
      <ErrorState
        title={t("staff.load_error")}
        requestId={requestIdOf(qualifications.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button variant="outline" onClick={() => void qualifications.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  const rows = qualifications.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="staff-qualifications">
      {canManage ? (
        <Button
          onClick={() => {
            setError(null);
            setForm({ ...EMPTY_FORM });
          }}
        >
          {t("staff.qualification.add")}
        </Button>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState title={t("staff.qualification.empty")} />
      ) : (
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t("staff.qualification.title")}>
          <table className="ui-table" data-testid="qualifications-table">
            <thead>
              <tr>
                <th scope="col">{t("staff.qualification.kind")}</th>
                <th scope="col">{t("staff.qualification.name")}</th>
                <th scope="col">{t("staff.qualification.institution")}</th>
                <th scope="col">{t("staff.qualification.start_date")}</th>
                <th scope="col">{t("staff.qualification.end_date")}</th>
                <th scope="col">{t("staff.common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((qualification) => (
                <tr key={qualification.id} data-testid={`qualification-row-${qualification.id}`}>
                  <td>{t(`staff.qualification.kind.${qualification.kind}`)}</td>
                  <td>{qualification.title}</td>
                  <td>{qualification.institution ?? t("staff.not_set")}</td>
                  <td>{qualification.start_date ?? t("staff.not_set")}</td>
                  <td>{qualification.end_date ?? t("staff.not_set")}</td>
                  <td>
                    {canManage ? (
                      <div className="flex flex-wrap gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setError(null);
                            setForm(formOf(qualification));
                          }}
                        >
                          {t("staff.qualification.edit")}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={remove.isPending}
                          onClick={() => remove.mutate(qualification.id)}
                        >
                          {t("staff.qualification.delete")}
                        </Button>
                      </div>
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
        title={t(form?.id ? "staff.qualification.edit" : "staff.qualification.add")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" form="qualification-form" disabled={save.isPending}>
              {save.isPending ? t("staff.qualification.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        {form ? (
          <form id="qualification-form" className="space-y-3" onSubmit={submit}>
            <Field label={t("staff.qualification.kind")}>
              <Select
                value={form.kind}
                onChange={(event) =>
                  setForm({ ...form, kind: event.target.value as QualificationKind })
                }
              >
                {QUALIFICATION_KINDS.map((value) => (
                  <option key={value} value={value}>
                    {t(`staff.qualification.kind.${value}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.qualification.name")}>
              <Input
                required
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
              />
            </Field>
            <Field label={t("staff.qualification.institution")}>
              <Input
                value={form.institution}
                onChange={(event) => setForm({ ...form, institution: event.target.value })}
              />
            </Field>
            <Field label={t("staff.qualification.field_of_study")}>
              <Input
                value={form.field_of_study}
                onChange={(event) => setForm({ ...form, field_of_study: event.target.value })}
              />
            </Field>
            <Field label={t("staff.qualification.start_date")}>
              <CalendarDatePicker
                value={form.start_date}
                onChange={(value) => setForm({ ...form, start_date: value })}
              />
            </Field>
            <Field label={t("staff.qualification.end_date")}>
              <CalendarDatePicker
                value={form.end_date}
                onChange={(value) => setForm({ ...form, end_date: value })}
              />
            </Field>
            <Field label={t("staff.qualification.result")}>
              <Input
                value={form.result}
                onChange={(event) => setForm({ ...form, result: event.target.value })}
              />
            </Field>
            <Field label={t("staff.qualification.notes")}>
              <Textarea
                rows={3}
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
