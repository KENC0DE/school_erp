import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Dialog, Field, Input, Select, Textarea } from "@erp/ui-web";
import { useState, type FormEvent } from "react";

import { NameFields, type NameValue } from "../../components/NameFields";
import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { STUDENTS } from "./queries";
import type { StudentDetail, StudentStatus } from "./types";

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

function namesOf(student: StudentDetail): NameValue {
  return {
    given_name_en: student.person.given_name_en ?? "",
    father_name_en: student.person.father_name_en ?? "",
    grandfather_name_en: student.person.grandfather_name_en ?? "",
    given_name_am: student.person.given_name_am ?? "",
    father_name_am: student.person.father_name_am ?? "",
    grandfather_name_am: student.person.grandfather_name_am ?? "",
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function StudentEditDialog({
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
  const [names, setNames] = useState<NameValue>(() => namesOf(student));
  const [sex, setSex] = useState(student.person.sex ?? "");
  const [dob, setDob] = useState(student.person.date_of_birth ?? "");
  const [phone, setPhone] = useState(student.person.phone ?? "");
  const [email, setEmail] = useState(student.person.email ?? "");
  const [address, setAddress] = useState(student.person.address ?? "");
  const [status, setStatus] = useState<StudentStatus>(student.status);
  const [admissionDate, setAdmissionDate] = useState(student.admission_date ?? "");
  const [exitDate, setExitDate] = useState(student.exit_date ?? "");
  const [exitReason, setExitReason] = useState(student.exit_reason ?? "");
  const [notes, setNotes] = useState(student.notes ?? "");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      api.patch<StudentDetail>(`${STUDENTS}/${student.id}`, {
        person: {
          ...Object.fromEntries(
            Object.entries(names).map(([key, value]) => [key, clean(value)]),
          ),
          sex: clean(sex),
          date_of_birth: clean(dob),
          phone: clean(phone),
          email: clean(email),
          address: clean(address),
        },
        status,
        admission_date: clean(admissionDate),
        exit_date: clean(exitDate),
        exit_reason: clean(exitReason),
        notes: clean(notes),
        row_version: student.row_version,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["students", "detail", student.id] });
      void queryClient.invalidateQueries({ queryKey: ["students", "list"] });
      onClose();
    },
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("students.edit.failed"));
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    save.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("students.edit.title")}
      closeLabel={t("common.close")}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" form="student-edit-form" disabled={save.isPending}>
            {save.isPending ? t("students.edit.saving") : t("common.save")}
          </Button>
        </>
      }
    >
      <form id="student-edit-form" className="space-y-4" onSubmit={submit}>
        <NameFields value={names} onChange={setNames} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("students.sex")}>
            <Select value={sex} onChange={(event) => setSex(event.target.value)}>
              <option value="">{t("students.sex.unspecified")}</option>
              <option value="male">{t("students.sex.male")}</option>
              <option value="female">{t("students.sex.female")}</option>
            </Select>
          </Field>
          <Field label={t("students.date_of_birth")}>
            <Input type="date" value={dob} onChange={(event) => setDob(event.target.value)} />
          </Field>
          <Field label={t("students.phone")}>
            <Input value={phone} onChange={(event) => setPhone(event.target.value)} />
          </Field>
          <Field label={t("students.email")}>
            <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </Field>
        </div>
        <Field label={t("students.address")}>
          <Input value={address} onChange={(event) => setAddress(event.target.value)} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("students.status")}>
            <Select
              value={status}
              onChange={(event) => setStatus(event.target.value as StudentStatus)}
            >
              {STATUSES.map((item) => (
                <option key={item} value={item}>
                  {t(`students.status.${item}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("students.admission_date")}>
            <Input
              type="date"
              value={admissionDate}
              onChange={(event) => setAdmissionDate(event.target.value)}
            />
          </Field>
          <Field label={t("students.exit_date")}>
            <Input type="date" value={exitDate} onChange={(event) => setExitDate(event.target.value)} />
          </Field>
          <Field label={t("students.exit_reason")}>
            <Input value={exitReason} onChange={(event) => setExitReason(event.target.value)} />
          </Field>
        </div>
        <Field label={t("students.notes")}>
          <Textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
        </Field>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}
