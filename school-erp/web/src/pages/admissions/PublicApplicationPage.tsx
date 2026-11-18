import { ApiRequestError } from "@erp/api-client";
import {
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Select,
} from "@erp/ui-web";
import { useEffect, useState, type FormEvent } from "react";

import { CustomFieldsForm } from "../../components/CustomFieldsForm";
import type { NameValue } from "../../components/NameFields";
import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { ApplicantFields, EMPTY_APPLICANT, type ApplicantDraft } from "./ApplicantFields";
import { GuardianEditor, newGuardian } from "./GuardianEditor";
import { personPayload } from "./personPayload";
import { ADMISSIONS, usePublicForm } from "./queries";
import type { GuardianDraft, PublicApplicationResult } from "./types";

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function guardianPayload(guardian: GuardianDraft): Record<string, unknown> {
  const names: NameValue = guardian.names;
  return {
    person: {
      given_name_en: clean(names.given_name_en),
      father_name_en: clean(names.father_name_en),
      grandfather_name_en: clean(names.grandfather_name_en),
      given_name_am: clean(names.given_name_am),
      father_name_am: clean(names.father_name_am),
      grandfather_name_am: clean(names.grandfather_name_am),
      phone: clean(guardian.phone),
      email: clean(guardian.email),
    },
    relationship: guardian.relationship,
    is_primary: guardian.is_primary,
    can_pickup: guardian.can_pickup,
  };
}

function hasName(guardian: GuardianDraft): boolean {
  return Boolean(
    clean(guardian.names.given_name_en) ||
      clean(guardian.names.given_name_am) ||
      clean(guardian.names.father_name_en) ||
      clean(guardian.names.father_name_am),
  );
}

/**
 * The optional public application page at `/apply`. It renders outside the
 * signed-in shell: the server decides whether it is open, hands out a
 * short-lived form token and applies the honeypot and rate limit on submit.
 */
export function PublicApplicationPage() {
  const { t } = useI18n();
  const form = usePublicForm();

  const [applicant, setApplicant] = useState<ApplicantDraft>({ ...EMPTY_APPLICANT });
  const [yearId, setYearId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [custom, setCustom] = useState<Record<string, unknown>>({});
  const [guardians, setGuardians] = useState<GuardianDraft[]>([
    newGuardian({ is_primary: true, relationship: "mother" }),
  ]);
  const [honeypot, setHoneypot] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PublicApplicationResult | null>(null);


  useEffect(() => {
    if (form.data === undefined) return;
    setSecondsLeft(form.data.min_seconds);
    if (form.data.min_seconds <= 0) return;
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => (current <= 0 ? 0 : current - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [form.data]);

  useEffect(() => {
    if (yearId || !form.data) return;
    if (form.data.years.length === 1) setYearId(form.data.years[0].id);
  }, [form.data, yearId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.data) return;
    setError(null);
    setBusy(true);
    try {
      const body: Record<string, unknown> = {
        form_token: form.data.form_token,
        website: honeypot,
        person: personPayload(applicant),
        year_id: yearId || null,
        level_id: levelId,
        custom,
        guardians: guardians.filter(hasName).map(guardianPayload),
      };
      const created = await api.post<PublicApplicationResult>(
        `${ADMISSIONS}/public/applications`,
        body,
      );
      setResult(created);
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("admissions.public.failed"));
    } finally {
      setBusy(false);
    }
  }

  if (form.isPending) {
    return (
      <main className="mx-auto max-w-2xl p-6">
        <LoadingState label={t("common.loading")} testId="public-apply-loading" />
      </main>
    );
  }

  if (form.isError || !form.data) {
    return (
      <main className="mx-auto max-w-2xl p-6">
        <Card>
          <CardContent className="p-6">
            <ErrorState
              title={t("admissions.public.unavailable")}
              requestId={requestIdOf(form.error)}
              requestIdLabel={t("common.request_id")}
              retry={
                <Button variant="outline" onClick={() => void form.refetch()}>
                  {t("common.retry")}
                </Button>
              }
              testId="public-apply-error"
            />
          </CardContent>
        </Card>
      </main>
    );
  }

  const data = form.data;

  if (!data.enabled) {
    return (
      <main className="mx-auto max-w-2xl space-y-4 p-6">
        <h1 className="text-lg font-semibold">{data.school_name || t("admissions.title")}</h1>
        <Card>
          <CardContent className="p-6">
            <EmptyState
              title={t("admissions.public.closed")}
              description={t("admissions.public.closed_hint")}
              testId="public-apply-closed"
            />
          </CardContent>
        </Card>
      </main>
    );
  }

  if (result) {
    return (
      <main className="mx-auto max-w-2xl space-y-4 p-6">
        <h1 className="text-lg font-semibold">{data.school_name || t("admissions.title")}</h1>
        <Card>
          <CardContent className="space-y-3 p-6" role="status" data-testid="public-apply-done">
            <h2 className="text-base font-semibold">{t("admissions.public.success_heading")}</h2>
            <p className="text-sm">
              {t("admissions.public.success", { number: result.application_number })}
            </p>
            <p className="text-sm text-muted-foreground">
              {t("admissions.public.success_hint", { name: result.full_name })}
            </p>
            <Button
              variant="outline"
              onClick={() => {
                setResult(null);
                setApplicant({ ...EMPTY_APPLICANT });
                setGuardians([newGuardian({ is_primary: true, relationship: "mother" })]);
                setCustom({});
                setHoneypot("");
                setSecondsLeft(data.min_seconds);
                void form.refetch();
              }}
            >
              {t("admissions.public.another")}
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  const canSubmit = secondsLeft === 0 && !busy && Boolean(levelId);

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold">{data.school_name || t("admissions.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("admissions.public.hint")}</p>
      </header>

      <form className="space-y-4" onSubmit={submit} noValidate>
        <Card>
          <CardContent className="space-y-4 p-4">
            <h2 className="text-sm font-semibold">{t("admissions.person")}</h2>
            <ApplicantFields value={applicant} onChange={setApplicant} disabled={busy} />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="grid gap-3 p-4 sm:grid-cols-2">
            {data.years.length > 1 ? (
              <Field label={t("admissions.year")}>
                <Select
                  data-testid="public-apply-year"
                  value={yearId}
                  disabled={busy}
                  onChange={(event) => setYearId(event.target.value)}
                >
                  <option value="">{t("admissions.filter.all_years")}</option>
                  {data.years.map((year) => (
                    <option key={year.id} value={year.id}>
                      {year.name}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : null}
            <Field label={t("admissions.level")}>
              <Select
                data-testid="public-apply-level"
                value={levelId}
                disabled={busy}
                onChange={(event) => setLevelId(event.target.value)}
              >
                <option value="">{t("admissions.public.choose_level")}</option>
                {data.levels.map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </Select>
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 p-4">
            <h2 className="text-sm font-semibold">{t("admissions.form.fields")}</h2>
            <CustomFieldsForm
              entityType="admission_application"
              definitions={data.fields}
              value={custom}
              onChange={setCustom}
              disabled={busy}
            />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <GuardianEditor
              guardians={guardians}
              onChange={setGuardians}
              requireGuardian={data.require_guardian}
            />
          </CardContent>
        </Card>

        {/* Honeypot: real people never see or fill this. */}
        <div className="ui-visually-hidden" aria-hidden="true">
          <label>
            {t("admissions.public.website")}
            <input
              tabIndex={-1}
              autoComplete="off"
              name="website"
              data-testid="public-apply-website"
              value={honeypot}
              onChange={(event) => setHoneypot(event.target.value)}
            />
          </label>
        </div>

        {error ? (
          <p className="text-sm text-destructive" role="alert" data-testid="public-apply-error-message">
            {error}
          </p>
        ) : null}

        {secondsLeft > 0 ? (
          <p className="text-sm text-muted-foreground" role="status" data-testid="public-apply-wait">
            {t("admissions.public.wait", { seconds: secondsLeft })}
          </p>
        ) : null}

        <Button type="submit" disabled={!canSubmit} data-testid="public-apply-submit">
          {busy ? t("admissions.public.saving") : t("admissions.public.submit")}
        </Button>
      </form>
    </main>
  );
}
