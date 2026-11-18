import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Field, Input, LoadingState, Textarea } from "@erp/ui-web";
import { useEffect, useState } from "react";

import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { STUDENTS } from "./queries";
import type { Medical, StudentDetail } from "./types";

const EMPTY: Omit<Medical, "id" | "student_id" | "row_version"> = {
  blood_type: "",
  allergies: "",
  chronic_conditions: "",
  medications: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  notes: "",
  consent_to_treat: false,
};

export function StudentMedical({
  student,
  canManage,
}: {
  student: StudentDetail;
  canManage: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(EMPTY);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const medical = useQuery({
    queryKey: ["students", "medical", student.id],
    queryFn: () => api.get<Medical | null>(`${STUDENTS}/${student.id}/medical`),
    retry: false,
  });

  useEffect(() => {
    if (medical.data) {
      setDraft({
        blood_type: medical.data.blood_type ?? "",
        allergies: medical.data.allergies ?? "",
        chronic_conditions: medical.data.chronic_conditions ?? "",
        medications: medical.data.medications ?? "",
        emergency_contact_name: medical.data.emergency_contact_name ?? "",
        emergency_contact_phone: medical.data.emergency_contact_phone ?? "",
        notes: medical.data.notes ?? "",
        consent_to_treat: medical.data.consent_to_treat,
      });
    }
  }, [medical.data]);

  const save = useMutation({
    mutationFn: () => api.put<Medical>(`${STUDENTS}/${student.id}/medical`, draft),
    onSuccess: () => {
      setSaved(true);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["students", "medical", student.id] });
      void queryClient.invalidateQueries({ queryKey: ["students", "detail", student.id] });
    },
    onError: (caught) => {
      setSaved(false);
      setError(caught instanceof ApiRequestError ? caught.message : t("students.medical.failed"));
    },
  });

  if (medical.isPending) {
    return <LoadingState label={t("students.medical.loading")} testId="medical-loading" />;
  }

  return (
    <div className="space-y-4" data-testid="student-medical">
      <fieldset className="grid gap-3 sm:grid-cols-2" disabled={!canManage}>
        <Field label={t("students.medical.blood_type")}>
          <Input
            value={draft.blood_type ?? ""}
            onChange={(event) => setDraft({ ...draft, blood_type: event.target.value })}
          />
        </Field>
        <Field label={t("students.medical.emergency_contact_name")}>
          <Input
            value={draft.emergency_contact_name ?? ""}
            onChange={(event) => setDraft({ ...draft, emergency_contact_name: event.target.value })}
          />
        </Field>
        <Field label={t("students.medical.emergency_contact_phone")}>
          <Input
            value={draft.emergency_contact_phone ?? ""}
            onChange={(event) => setDraft({ ...draft, emergency_contact_phone: event.target.value })}
          />
        </Field>
        <Field label={t("students.medical.consent_to_treat")}>
          <input
            type="checkbox"
            checked={draft.consent_to_treat}
            onChange={(event) => setDraft({ ...draft, consent_to_treat: event.target.checked })}
          />
        </Field>
        <Field label={t("students.medical.allergies")} className="sm:col-span-2">
          <Textarea
            rows={2}
            value={draft.allergies ?? ""}
            onChange={(event) => setDraft({ ...draft, allergies: event.target.value })}
          />
        </Field>
        <Field label={t("students.medical.chronic_conditions")} className="sm:col-span-2">
          <Textarea
            rows={2}
            value={draft.chronic_conditions ?? ""}
            onChange={(event) => setDraft({ ...draft, chronic_conditions: event.target.value })}
          />
        </Field>
        <Field label={t("students.medical.medications")} className="sm:col-span-2">
          <Textarea
            rows={2}
            value={draft.medications ?? ""}
            onChange={(event) => setDraft({ ...draft, medications: event.target.value })}
          />
        </Field>
        <Field label={t("students.notes")} className="sm:col-span-2">
          <Textarea
            rows={2}
            value={draft.notes ?? ""}
            onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
          />
        </Field>
      </fieldset>

      {canManage ? (
        <div className="flex items-center gap-3">
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? t("students.medical.saving") : t("common.save")}
          </Button>
          {saved ? (
            <p className="text-sm text-primary" role="status">
              {t("students.medical.saved")}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t("students.medical.restricted")}</p>
      )}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
