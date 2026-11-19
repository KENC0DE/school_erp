import { ApiRequestError } from "@erp/api-client";
import {
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Page,
  PageHeader,
  Select,
} from "@erp/ui-web";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { CustomFieldsForm } from "../../components/CustomFieldsForm";
import type { NameValue } from "../../components/NameFields";
import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { hasPermission, useLevels, useSections, useYears } from "../students/queries";
import { ApplicantFields, EMPTY_APPLICANT, type ApplicantDraft } from "./ApplicantFields";
import { GuardianEditor } from "./GuardianEditor";
import { personPayload, draftFromPerson } from "./personPayload";
import { ADMISSIONS, useAdmissionForm, useApplication } from "./queries";
import type { ApplicationDetail, DuplicateWarning, GuardianDraft } from "./types";

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
    wants_account: guardian.wants_account,
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

/** Take a new application, or edit one that is still open for changes. */
export function ApplicationFormPage({ mode }: { mode: "new" | "edit" }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const params = useParams<{ id: string }>();
  const applicationId = mode === "edit" ? (params.id ?? null) : null;
  const canManage = hasPermission(user?.permissions, "admissions.manage");

  const form = useAdmissionForm();
  const detail = useApplication(applicationId);
  const years = useYears();
  const levels = useLevels();

  const [applicant, setApplicant] = useState<ApplicantDraft>({ ...EMPTY_APPLICANT });
  const [yearId, setYearId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [score, setScore] = useState("");
  const [appliedOn, setAppliedOn] = useState("");
  const [notes, setNotes] = useState("");
  const [custom, setCustom] = useState<Record<string, unknown>>({});
  const [guardians, setGuardians] = useState<GuardianDraft[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateWarning[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadedId, setLoadedId] = useState<string | null>(null);

  const sections = useSections(yearId, levelId);

  useEffect(() => {
    if (!detail.data || loadedId === detail.data.id) return;
    setApplicant(draftFromPerson(detail.data.person));
    setYearId(detail.data.year_id);
    setLevelId(detail.data.level_id);
    setSectionId(detail.data.section_id ?? "");
    setScore(detail.data.entrance_test_score === null ? "" : String(detail.data.entrance_test_score));
    setAppliedOn(detail.data.applied_on ?? "");
    setNotes(detail.data.notes ?? "");
    setCustom(detail.data.custom ?? {});
    setLoadedId(detail.data.id);
  }, [detail.data, loadedId]);

  useEffect(() => {
    if (mode !== "new" || yearId) return;
    const current = years.data?.items.find((year) => year.id === years.data?.current_year_id);
    const firstOpen = years.data?.items.find((year) => year.status !== "closed");
    const chosen = current ?? firstOpen;
    if (chosen) setYearId(chosen.id);
  }, [mode, yearId, years.data]);

  if (!canManage) {
    return (
      <Page>
        <Card>
          <CardContent className="p-6">
            <EmptyState title={t("admissions.permission_denied")} />
          </CardContent>
        </Card>
      </Page>
    );
  }

  if (mode === "edit" && detail.isPending) {
    return (
      <Page>
        <LoadingState label={t("admissions.loading")} testId="admission-edit-loading" />
      </Page>
    );
  }

  if (mode === "edit" && (detail.isError || !detail.data)) {
    return (
      <Page>
        <Card>
          <CardContent className="p-6">
            <ErrorState
              title={t("admissions.load_error")}
              requestId={requestIdOf(detail.error)}
              requestIdLabel={t("common.request_id")}
              retry={
                <Button variant="outline" onClick={() => void detail.refetch()}>
                  {t("common.retry")}
                </Button>
              }
              testId="admission-edit-error"
            />
          </CardContent>
        </Card>
      </Page>
    );
  }

  const locked =
    mode === "edit" && detail.data
      ? !["applied", "reviewed", "test", "offered"].includes(detail.data.status)
      : false;

  const yearOptions = (years.data?.items ?? []).filter((year) => year.status !== "closed");

  function buildPayload() {
    const body: Record<string, unknown> = {
      person: personPayload(applicant),
      year_id: yearId || null,
      level_id: levelId,
      section_id: sectionId || null,
      applied_on: appliedOn || null,
      notes: clean(notes),
      custom,
    };
    if (form.data?.entrance_test_enabled && score.trim() !== "") {
      body.entrance_test_score = Number(score);
    }
    return body;
  }

  async function save(skipDuplicateCheck = false) {
    setError(null);
    setBusy(true);
    try {
      if (mode === "edit" && detail.data) {
        const patch = buildPayload();
        delete patch.person_id;
        await api.patch<ApplicationDetail>(`${ADMISSIONS}/${detail.data.id}`, {
          ...patch,
          row_version: detail.data.row_version,
        });
        navigate(`/admissions/${detail.data.id}`);
        return;
      }

      const body = {
        ...buildPayload(),
        guardians: guardians.filter(hasName).map(guardianPayload),
        source: "office",
      };
      if (!skipDuplicateCheck) {
        const preview = await api.post<{ duplicate_warnings: DuplicateWarning[] }>(
          `${ADMISSIONS}/preview`,
          body,
        );
        if (preview.duplicate_warnings.length > 0) {
          setDuplicates(preview.duplicate_warnings);
          return;
        }
      }
      const created = await api.post<ApplicationDetail>(ADMISSIONS, body);
      navigate(`/admissions/${created.id}`);
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t(
        mode === "edit" ? "admissions.edit.failed" : "admissions.new.failed",
      ));
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void save();
  }

  return (
    <Page>
      <PageHeader
        title={mode === "edit" ? t("admissions.edit.title") : t("admissions.new.title")}
        description={mode === "edit" ? t("admissions.form.hint") : t("admissions.new.hint")}
        actions={
          <Button variant="outline" onClick={() => navigate("/admissions")}>
            {t("admissions.back_to_list")}
          </Button>
        }
      />

      {locked ? (
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-destructive" role="status">
              {t("admissions.edit.locked")}
            </p>
          </CardContent>
        </Card>
      ) : null}

      <form className="space-y-4" onSubmit={submit} noValidate>
        <Card>
          <CardContent className="space-y-4 p-4">
            <h2 className="text-sm font-semibold">{t("admissions.person")}</h2>
            <ApplicantFields value={applicant} onChange={setApplicant} disabled={locked || busy} />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label={t("admissions.year")}>
              <Select
                data-testid="admission-year"
                value={yearId}
                disabled={locked || busy}
                onChange={(event) => {
                  setYearId(event.target.value);
                  setSectionId("");
                }}
              >
                <option value="">{t("admissions.filter.all_years")}</option>
                {yearOptions.map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("admissions.level")}>
              <Select
                data-testid="admission-level"
                value={levelId}
                disabled={locked || busy}
                onChange={(event) => {
                  setLevelId(event.target.value);
                  setSectionId("");
                }}
              >
                <option value="">{t("admissions.filter.all_levels")}</option>
                {(levels.data?.items ?? []).map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("admissions.section")}>
              <Select
                data-testid="admission-section"
                value={sectionId}
                disabled={locked || busy || !yearId || !levelId}
                onChange={(event) => setSectionId(event.target.value)}
              >
                <option value="">{t("admissions.section.auto")}</option>
                {(sections.data?.items ?? [])
                  .filter((section) => section.is_active)
                  .map((section) => (
                    <option key={section.id} value={section.id}>
                      {section.code}
                    </option>
                  ))}
              </Select>
            </Field>
            <Field label={t("admissions.applied_on")}>
              <Input
                type="date"
                data-testid="admission-applied-on"
                value={appliedOn}
                disabled={locked || busy}
                onChange={(event) => setAppliedOn(event.target.value)}
              />
            </Field>
            {form.data?.entrance_test_enabled ? (
              <Field label={t("admissions.entrance_test.score")}>
                <Input
                  type="number"
                  min={0}
                  max={form.data.entrance_test_max_score}
                  step={1}
                  data-testid="admission-score"
                  value={score}
                  disabled={locked || busy}
                  onChange={(event) => setScore(event.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  {t("admissions.entrance_test.max")}: {form.data.entrance_test_max_score}
                  {form.data.entrance_test_pass_score === null
                    ? ""
                    : ` · ${t("admissions.entrance_test.pass")}: ${form.data.entrance_test_pass_score}`}
                </p>
              </Field>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 p-4">
            <h2 className="text-sm font-semibold">{t("admissions.notes")}</h2>
            <label className="block space-y-1 text-sm">
              <span className="ui-visually-hidden">{t("admissions.notes")}</span>
              <textarea
                className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                data-testid="admission-notes"
                maxLength={4000}
                value={notes}
                disabled={locked || busy}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 p-4">
            <h2 className="text-sm font-semibold">{t("admissions.form.fields")}</h2>
            {form.isPending ? (
              <p className="text-sm text-muted-foreground" role="status">
                {t("common.loading")}
              </p>
            ) : (
              <CustomFieldsForm
                entityType={form.data?.entity_type ?? "admission_application"}
                definitions={form.data?.fields ?? []}
                value={custom}
                onChange={setCustom}
                disabled={locked || busy}
              />
            )}
          </CardContent>
        </Card>

        {mode === "new" ? (
          <Card>
            <CardContent className="p-4">
              <GuardianEditor
                guardians={guardians}
                onChange={setGuardians}
                requireGuardian={form.data?.require_guardian ?? true}
                showAccountOption
              />
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-4">
              <h2 className="text-sm font-semibold">{t("admissions.guardians")}</h2>
              <p className="text-sm text-muted-foreground">{t("admissions.edit.guardians_hint")}</p>
            </CardContent>
          </Card>
        )}

        {duplicates.length > 0 ? (
          <Card>
            <CardContent className="space-y-2 p-4" role="alert">
              <p className="text-sm font-semibold">{t("admissions.duplicate.title")}</p>
              <p className="text-sm text-muted-foreground">{t("admissions.duplicate.hint")}</p>
              <ul className="space-y-1 text-sm">
                {duplicates.map((warning) => (
                  <li key={warning.person.id}>
                    {warning.person.full_name} ·{" "}
                    {t("admissions.duplicate.similarity", {
                      percent: Math.round(warning.similarity * 100),
                    })}
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-2">
                <Button variant="destructive" onClick={() => void save(true)} disabled={busy}>
                  {t("admissions.new.anyway")}
                </Button>
                <Button variant="ghost" onClick={() => setDuplicates([])}>
                  {t("common.cancel")}
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {error ? (
          <p className="text-sm text-destructive" role="alert" data-testid="admission-form-error">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy || locked} data-testid="admission-submit">
            {mode === "edit"
              ? busy
                ? t("admissions.edit.saving")
                : t("admissions.edit.submit")
              : busy
                ? t("admissions.new.saving")
                : t("admissions.new.submit")}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => navigate(mode === "edit" && applicationId ? `/admissions/${applicationId}` : "/admissions")}
          >
            {t("common.cancel")}
          </Button>
        </div>
      </form>
    </Page>
  );
}
