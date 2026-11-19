import { ApiRequestError } from "@erp/api-client";
import { useMutation } from "@tanstack/react-query";
import { Button, Dialog, Field, Input, Select, Textarea } from "@erp/ui-web";
import { useState, type ChangeEvent, type FormEvent } from "react";

import { EMPTY_NAME, NameFields, type NameValue } from "../../components/NameFields";
import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { STUDENTS, useLevels, useSections, useYears } from "./queries";
import type { DuplicateWarning, StudentRegisterOut, StudentSummary, UploadedPhoto } from "./types";

interface GuardianDraft {
  relationship: string;
  is_primary: boolean;
  can_pickup: boolean;
  names: NameValue;
}

const EMPTY_GUARDIAN: GuardianDraft = {
  relationship: "mother",
  is_primary: true,
  can_pickup: true,
  names: { ...EMPTY_NAME },
};

const RELATIONSHIPS = ["mother", "father", "guardian", "grandparent", "sibling", "other"] as const;

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function personPayload(names: NameValue, extra: Record<string, unknown> = {}) {
  const payload: Record<string, unknown> = { ...extra };
  for (const [key, value] of Object.entries(names)) {
    payload[key] = clean(value);
  }
  return payload;
}

export function StudentRegisterDialog({
  open,
  onClose,
  onRegistered,
}: {
  open: boolean;
  onClose: () => void;
  onRegistered: (student: StudentSummary) => void;
}) {
  const { t } = useI18n();
  const years = useYears();
  const levels = useLevels();

  const [names, setNames] = useState<NameValue>({ ...EMPTY_NAME });
  const [sex, setSex] = useState("");
  const [dob, setDob] = useState("");
  const [placeOfBirth, setPlaceOfBirth] = useState("");
  const [nationality, setNationality] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [studentNumber, setStudentNumber] = useState("");
  const [admissionDate, setAdmissionDate] = useState("");
  const [notes, setNotes] = useState("");
  const [yearId, setYearId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [rollNumber, setRollNumber] = useState("");
  const [guardianEnabled, setGuardianEnabled] = useState(false);
  const [guardian, setGuardian] = useState<GuardianDraft>({ ...EMPTY_GUARDIAN });
  const [photoId, setPhotoId] = useState<string | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [warnings, setWarnings] = useState<DuplicateWarning[]>([]);
  const [awaitingConfirm, setAwaitingConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sections = useSections(yearId, levelId);

  const register = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.post<StudentRegisterOut>(STUDENTS, payload),
    onSuccess: (student) => {
      reset();
      onRegistered(student);
    },
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("students.register.failed"));
    },
  });

  function reset() {
    setNames({ ...EMPTY_NAME });
    setSex("");
    setDob("");
    setPlaceOfBirth("");
    setNationality("");
    setPhone("");
    setEmail("");
    setAddress("");
    setStudentNumber("");
    setAdmissionDate("");
    setNotes("");
    setYearId("");
    setLevelId("");
    setSectionId("");
    setRollNumber("");
    setGuardianEnabled(false);
    setGuardian({ ...EMPTY_GUARDIAN, names: { ...EMPTY_NAME } });
    setPhotoId(null);
    setPhotoUrl(null);
    setPhotoError(null);
    setWarnings([]);
    setAwaitingConfirm(false);
    setError(null);
  }

  function cancel() {
    reset();
    onClose();
  }

  function payload(): Record<string, unknown> {
    const person = personPayload(names, {
      sex: clean(sex),
      date_of_birth: clean(dob),
      place_of_birth: clean(placeOfBirth),
      nationality: clean(nationality),
      phone: clean(phone),
      email: clean(email),
      address: clean(address),
      photo_file_id: photoId,
    });
    const body: Record<string, unknown> = {
      person,
      student_number: clean(studentNumber),
      admission_date: clean(admissionDate),
      notes: clean(notes),
    };
    if (yearId && levelId) {
      body.enrollment = {
        year_id: yearId,
        level_id: levelId,
        section_id: sectionId || null,
        roll_number: clean(rollNumber),
        status: "active",
      };
    }
    if (guardianEnabled) {
      body.guardians = [
        {
          person: personPayload(guardian.names),
          relationship: guardian.relationship,
          is_primary: guardian.is_primary,
          can_pickup: guardian.can_pickup,
        },
      ];
    }
    return body;
  }

  async function checkDuplicates(): Promise<DuplicateWarning[]> {
    const person = personPayload(names, { date_of_birth: clean(dob) });
    if (!person.date_of_birth || !person.given_name_en) return [];
    try {
      const result = await api.post<{ duplicate_warnings: DuplicateWarning[] }>(
        `${STUDENTS}/duplicate-check`,
        { person },
      );
      return result.duplicate_warnings;
    } catch {
      return [];
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!awaitingConfirm) {
      const found = await checkDuplicates();
      if (found.length > 0) {
        setWarnings(found);
        setAwaitingConfirm(true);
        return;
      }
    }
    register.mutate(payload());
  }

  async function uploadPhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setPhotoError(null);
    setUploadingPhoto(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const uploaded = await api.postForm<UploadedPhoto>(`${STUDENTS}/photos`, form);
      setPhotoId(uploaded.id);
      setPhotoUrl(uploaded.url);
    } catch (caught) {
      setPhotoError(caught instanceof ApiRequestError ? caught.message : t("students.photo.failed"));
    } finally {
      setUploadingPhoto(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={cancel}
      title={t("students.register.title")}
      description={t("students.register.hint")}
      wide
      closeLabel={t("common.close")}
      footer={
        <>
          <Button variant="ghost" onClick={cancel}>
            {t("common.cancel")}
          </Button>
          <Button
            type="submit"
            form="student-register-form"
            disabled={register.isPending || uploadingPhoto}
          >
            {register.isPending
              ? t("students.register.saving")
              : awaitingConfirm
                ? t("students.register.anyway")
                : t("students.register.submit")}
          </Button>
        </>
      }
    >
      <form id="student-register-form" className="space-y-5" onSubmit={(event) => void submit(event)}>
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
          <Field label={t("students.place_of_birth")}>
            <Input value={placeOfBirth} onChange={(event) => setPlaceOfBirth(event.target.value)} />
          </Field>
          <Field label={t("students.nationality")}>
            <Input value={nationality} onChange={(event) => setNationality(event.target.value)} />
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
          <Field label={t("students.number")} hint={t("students.register.number_hint")}>
            <Input
              data-testid="student-number"
              value={studentNumber}
              onChange={(event) => setStudentNumber(event.target.value)}
            />
          </Field>
          <Field label={t("students.admission_date")}>
            <Input
              type="date"
              value={admissionDate}
              onChange={(event) => setAdmissionDate(event.target.value)}
            />
          </Field>
        </div>

        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold">{t("students.register.enrollment")}</legend>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("students.enrollment.year")}>
              <Select
                data-testid="register-year"
                value={yearId}
                onChange={(event) => {
                  setYearId(event.target.value);
                  setSectionId("");
                }}
              >
                <option value="">{t("students.register.no_enrollment")}</option>
                {(years.data?.items ?? []).map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("students.enrollment.level")}>
              <Select
                data-testid="register-level"
                value={levelId}
                disabled={!yearId}
                onChange={(event) => {
                  setLevelId(event.target.value);
                  setSectionId("");
                }}
              >
                <option value="">{t("students.register.no_level")}</option>
                {(levels.data?.items ?? []).map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("students.enrollment.section")}>
              <Select
                value={sectionId}
                disabled={!yearId || !levelId}
                onChange={(event) => setSectionId(event.target.value)}
              >
                <option value="">{t("students.register.no_section")}</option>
                {(sections.data?.items ?? []).map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.code}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label={t("students.enrollment.roll_number")}>
            <Input value={rollNumber} onChange={(event) => setRollNumber(event.target.value)} />
          </Field>
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold">{t("students.photo.title")}</legend>
          <div className="flex flex-wrap items-center gap-3">
            {photoUrl ? (
              <img
                src={photoUrl}
                alt={t("students.photo.preview")}
                className="h-20 w-20 rounded-md border border-border object-cover"
              />
            ) : null}
            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("students.photo.choose")}</span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="block text-sm text-muted-foreground"
                onChange={(event) => void uploadPhoto(event)}
              />
            </label>
            {uploadingPhoto ? <p className="text-sm text-muted-foreground">{t("students.photo.uploading")}</p> : null}
          </div>
          {photoError ? (
            <p role="alert" className="text-sm text-destructive">
              {photoError}
            </p>
          ) : null}
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold">{t("students.guardians")}</legend>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={guardianEnabled}
              onChange={(event) => setGuardianEnabled(event.target.checked)}
            />
            {t("students.register.add_guardian")}
          </label>
          {guardianEnabled ? (
            <div className="space-y-3 rounded-md border border-border p-3">
              <NameFields
                value={guardian.names}
                onChange={(next) => setGuardian((current) => ({ ...current, names: next }))}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={t("students.guardian.relationship")}>
                  <Select
                    value={guardian.relationship}
                    onChange={(event) =>
                      setGuardian((current) => ({ ...current, relationship: event.target.value }))
                    }
                  >
                    {RELATIONSHIPS.map((relationship) => (
                      <option key={relationship} value={relationship}>
                        {t(`students.relationship.${relationship}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="flex flex-col gap-2 pt-6 text-sm">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={guardian.is_primary}
                      onChange={(event) =>
                        setGuardian((current) => ({ ...current, is_primary: event.target.checked }))
                      }
                    />
                    {t("students.guardian.primary")}
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={guardian.can_pickup}
                      onChange={(event) =>
                        setGuardian((current) => ({ ...current, can_pickup: event.target.checked }))
                      }
                    />
                    {t("students.guardian.can_pickup")}
                  </label>
                </div>
              </div>
            </div>
          ) : null}
        </fieldset>

        <Field label={t("students.notes")}>
          <Textarea value={notes} rows={2} onChange={(event) => setNotes(event.target.value)} />
        </Field>

        {warnings.length > 0 ? (
          <div className="rounded-md border border-warning-border bg-warning-surface p-3" role="alert">
            <p className="text-sm font-semibold">{t("students.duplicate.title")}</p>
            <p className="text-xs text-muted-foreground">{t("students.duplicate.hint")}</p>
            <ul className="mt-2 space-y-1 text-sm">
              {warnings.map((warning) => (
                <li key={warning.person.id}>
                  {warning.person.full_name}
                  {warning.person.date_of_birth ? ` · ${warning.person.date_of_birth}` : ""}
                  <span className="text-muted-foreground"> — {t("students.duplicate.similarity", { percent: Math.round(warning.similarity * 100) })}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}
