import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Dialog, Field, Input, Select, Textarea } from "@erp/ui-web";
import { useState, type FormEvent } from "react";

import { requestIdOf } from "../../lib/errors";
import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { STUDENTS } from "./queries";
import type {
  StudentDetail,
  StudentStatusAction,
  StudentStatusChangeInput,
  StudentStatusChangeOut,
} from "./types";

const ALLOWED: Record<string, StudentStatusAction[]> = {
  active: ["transfer_out", "withdraw", "graduate"],
  promoted: ["transfer_out", "withdraw", "graduate"],
  repeating: ["transfer_out", "withdraw", "graduate"],
  graduated: ["alumni"],
  transferred_out: ["reinstate"],
  withdrawn: ["reinstate"],
};
const REASON_REQUIRED = new Set<StudentStatusAction>([
  "transfer_out",
  "withdraw",
]);

export function allowedStatusActions(status: string): StudentStatusAction[] {
  return ALLOWED[status] ?? [];
}

export function StudentStatusDialog({
  student,
  open,
  onClose,
}: {
  student: StudentDetail;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const options = allowedStatusActions(student.status);
  const [action, setAction] = useState<StudentStatusAction>(
    options[0] ?? "reinstate",
  );
  const [exitDate, setExitDate] = useState("");
  const [exitReason, setExitReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (body: StudentStatusChangeInput) =>
      api.post<StudentStatusChangeOut>(
        `${STUDENTS}/${student.id}/status`,
        body,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["students", "detail", student.id],
      });
      void queryClient.invalidateQueries({ queryKey: ["students", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
      onClose();
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError
          ? caught.message
          : t("students.progress.status.failed"),
      );
    },
  });

  if (!open) return null;

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    save.mutate({
      action,
      ...(exitDate ? { exit_date: exitDate } : {}),
      ...(exitReason.trim() ? { exit_reason: exitReason.trim() } : {}),
      row_version: student.row_version,
    });
  }

  const needsReason = REASON_REQUIRED.has(action);
  const disabled =
    options.length === 0 ||
    (needsReason && !exitReason.trim()) ||
    save.isPending;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("students.progress.status.title")}
      description={t("students.progress.status.current", {
        status: t(`students.status.${student.status}`),
      })}
      closeLabel={t("common.close")}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" form="student-status-form" disabled={disabled}>
            {save.isPending
              ? t("students.progress.status.saving")
              : t("students.progress.status.submit")}
          </Button>
        </>
      }
    >
      <form
        id="student-status-form"
        className="space-y-4"
        onSubmit={submit}
        data-testid="student-status-form"
      >
        <Field label={t("students.progress.status.action")}>
          <Select
            data-testid="student-status-action"
            value={action}
            onChange={(event) =>
              setAction(event.target.value as StudentStatusAction)
            }
          >
            {options.map((option) => (
              <option key={option} value={option}>
                {t(`students.progress.status.action.${option}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("students.progress.status.exit_date")}>
          <Input
            type="date"
            data-testid="student-status-exit-date"
            value={exitDate}
            onChange={(event) => setExitDate(event.target.value)}
          />
        </Field>
        <Field
          label={t("students.progress.status.exit_reason")}
          hint={t("students.progress.status.reason_hint")}
          required={needsReason}
        >
          <Textarea
            data-testid="student-status-exit-reason"
            value={exitReason}
            onChange={(event) => setExitReason(event.target.value)}
          />
        </Field>
        {error ? (
          <p
            className="text-sm text-destructive"
            role="alert"
            data-testid="student-status-error"
          >
            {error}
            {requestIdOf(save.error) ? (
              <span className="block text-xs text-muted-foreground">
                {t("common.request_id")}: {requestIdOf(save.error)}
              </span>
            ) : null}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}
