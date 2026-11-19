import { ApiRequestError } from "@erp/api-client";
import { useQueryClient } from "@tanstack/react-query";
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
} from "@erp/ui-web";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Badge } from "../../components/ui/Badge";
import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { hasPermission } from "../students/queries";
import { ApplicationDocuments } from "./ApplicationDocuments";
import { ADMISSIONS, useApplication, useAdmissionForm, useConversionPreview } from "./queries";
import type {
  AdmissionStatus,
  ApplicationDetail,
  ConversionOut,
  ConversionPreview,
  DecisionOut,
  DecisionStatus,
} from "./types";

const TRANSITIONS: Record<AdmissionStatus, DecisionStatus[]> = {
  applied: ["reviewed", "rejected", "withdrawn"],
  reviewed: ["test", "offered", "rejected", "withdrawn"],
  test: ["offered", "rejected", "withdrawn"],
  offered: ["accepted", "rejected", "withdrawn"],
  accepted: ["withdrawn"],
  enrolled: [],
  rejected: [],
  withdrawn: [],
};

const DECISION_KEY: Record<DecisionStatus, string> = {
  reviewed: "admissions.decision.review",
  test: "admissions.decision.test",
  offered: "admissions.decision.offer",
  accepted: "admissions.decision.accept",
  rejected: "admissions.decision.reject",
  withdrawn: "admissions.decision.withdraw",
};

function statusVariant(status: AdmissionStatus): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "accepted" || status === "enrolled") return "success";
  if (status === "offered" || status === "test") return "warning";
  if (status === "rejected" || status === "withdrawn") return "danger";
  if (status === "reviewed") return "info";
  return "neutral";
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value || "—"}</dd>
    </div>
  );
}

function amharicName(person: ApplicationDetail["person"]): string {
  return [person.given_name_am, person.father_name_am, person.grandfather_name_am]
    .filter(Boolean)
    .join(" ");
}

export function ApplicationProfilePage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const params = useParams<{ id: string }>();
  const applicationId = params.id ?? null;
  const queryClient = useQueryClient();

  const canView = hasPermission(user?.permissions, "admissions.view");
  const canManage = hasPermission(user?.permissions, "admissions.manage");
  const canDecide = hasPermission(user?.permissions, "admissions.decide");

  const application = useApplication(applicationId);
  const form = useAdmissionForm();
  const detail = application.data;
  const conversion = useConversionPreview(
    applicationId,
    Boolean(detail && detail.status === "accepted" && !detail.student_id),
  );

  const [score, setScore] = useState("");
  const [decisionNotes, setDecisionNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [converted, setConverted] = useState<ConversionOut | null>(null);
  const [createAccounts, setCreateAccounts] = useState(true);

  if (!canView) {
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

  if (application.isPending) {
    return (
      <Page>
        <LoadingState label={t("admissions.loading")} testId="admission-profile-loading" />
      </Page>
    );
  }

  if (application.isError || !detail) {
    return (
      <Page>
        <Card>
          <CardContent className="p-6">
            <ErrorState
              title={t("admissions.load_error")}
              requestId={requestIdOf(application.error)}
              requestIdLabel={t("common.request_id")}
              retry={
                <Button variant="outline" onClick={() => void application.refetch()}>
                  {t("common.retry")}
                </Button>
              }
              testId="admission-profile-error"
            />
          </CardContent>
        </Card>
      </Page>
    );
  }

  const record: ApplicationDetail = detail;
  const allowed = TRANSITIONS[record.status] ?? [];
  const editable = ["applied", "reviewed", "test", "offered"].includes(record.status);

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["admissions"] });
  }

  async function decide(status: DecisionStatus) {
    setError(null);
    setBusy(status);
    try {
      const body: Record<string, unknown> = {
        status,
        row_version: record.row_version,
      };
      if (score.trim() !== "") body.entrance_test_score = Number(score);
      if (decisionNotes.trim() !== "") body.notes = decisionNotes.trim();
      const result = await api.post<DecisionOut>(`${ADMISSIONS}/${record.id}/decision`, body);
      setScore("");
      setDecisionNotes("");
      queryClient.setQueryData(["admissions", "detail", record.id], result.application);
      refresh();
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("admissions.decision.failed"));
    } finally {
      setBusy(null);
    }
  }

  async function convert() {
    setError(null);
    setBusy("convert");
    try {
      const result = await api.post<ConversionOut>(`${ADMISSIONS}/${record.id}/convert`, {
        row_version: record.row_version,
        create_guardian_accounts: createAccounts,
      });
      setConverted(result);
      queryClient.setQueryData(["admissions", "detail", record.id], result.application);
      refresh();
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("admissions.conversion.failed"));
    } finally {
      setBusy(null);
    }
  }

  const customFields = form.data?.fields ?? [];

  return (
    <Page>
      <PageHeader
        title={`${detail.application_number} · ${detail.person.full_name}`}
        description={t("admissions.intro")}
        actions={
          <div className="flex flex-wrap gap-2">
            {editable && canManage ? (
              <Button
                variant="outline"
                data-testid="admission-edit-open"
                onClick={() => navigate(`/admissions/${detail.id}/edit`)}
              >
                {t("admissions.edit.open")}
              </Button>
            ) : null}
            <Button variant="ghost" onClick={() => navigate("/admissions")}>
              {t("admissions.back_to_list")}
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={statusVariant(detail.status)}>
          {t(`admissions.status.${detail.status}`)}
        </Badge>
        <span className="text-sm text-muted-foreground">
          {t("admissions.source")}: {t(`admissions.source.${detail.source}`)}
        </span>
        {detail.student_id ? (
          <Link className="ui-link text-sm" to={`/students/${detail.student_id}`}>
            {t("admissions.student")}: {detail.student_number}
          </Link>
        ) : null}
      </div>

      <Card>
        <CardContent className="p-4">
          <h2 className="mb-3 text-sm font-semibold">{t("admissions.person")}</h2>
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Row label={t("admissions.person")} value={detail.person.full_name} />
            <Row label={t("name.amharic")} value={amharicName(detail.person)} />
            <Row label={t("admissions.year")} value={detail.year_name} />
            <Row
              label={t("admissions.level")}
              value={[detail.level_name, detail.section_code].filter(Boolean).join(" · ")}
            />
            <Row
              label={t("admissions.applied_on")}
              value={detail.applied_on ?? t("admissions.not_set")}
            />
            <Row label={t("admissions.phone")} value={detail.person.phone} />
            <Row label={t("admissions.email")} value={detail.person.email} />
            <Row label={t("admissions.date_of_birth")} value={detail.person.date_of_birth} />
          </dl>
          {detail.notes ? (
            <div className="mt-3 space-y-1 border-t border-border pt-3">
              <p className="text-xs text-muted-foreground">{t("admissions.notes")}</p>
              <p className="whitespace-pre-line text-sm">{detail.notes}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <h2 className="mb-3 text-sm font-semibold">{t("admissions.guardians")}</h2>
          {detail.guardians.length === 0 ? (
            <EmptyState title={t("admissions.guardian.empty")} />
          ) : (
            <ul className="space-y-2">
              {detail.guardians.map((guardian) => (
                <li
                  key={guardian.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
                  data-testid={`admission-guardian-${guardian.id}`}
                >
                  <span className="text-sm">
                    {guardian.person.full_name} ·{" "}
                    {t(`admissions.relationship.${guardian.relationship}`)}
                    {guardian.is_primary ? ` · ${t("admissions.guardian.primary")}` : ""}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {guardian.person.phone ?? guardian.person.email ?? ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {customFields.length > 0 ? (
        <Card>
          <CardContent className="p-4">
            <h2 className="mb-3 text-sm font-semibold">{t("admissions.form.fields")}</h2>
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {customFields.map((field) => {
                const value = detail.custom[field.key];
                const shown = Array.isArray(value)
                  ? value.join(", ")
                  : value === true
                    ? t("common.yes")
                    : value === false
                      ? t("common.no")
                      : value === undefined || value === null || value === ""
                        ? null
                        : String(value);
                return <Row key={field.id} label={t(field.label_key)} value={shown} />;
              })}
            </dl>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="space-y-3 p-4">
          <h2 className="text-sm font-semibold">{t("admissions.decision.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("admissions.decision.hint")}</p>

          {form.data?.entrance_test_enabled ? (
            <p className="text-sm" data-testid="admission-test-state">
              {t("admissions.entrance_test")}: {
                detail.test_passed === true
                  ? t("admissions.entrance_test.passed")
                  : detail.test_passed === false
                    ? t("admissions.entrance_test.failed")
                    : detail.entrance_test_score === null
                      ? t("admissions.entrance_test.not_taken")
                      : t("admissions.entrance_test.pending")
              }
              {detail.entrance_test_score === null
                ? ""
                : ` · ${detail.entrance_test_score}/${detail.test_max_score}`}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">{t("admissions.entrance_test.disabled")}</p>
          )}

          {detail.decision_notes ? (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">{t("admissions.decision_notes")}</p>
              <p className="whitespace-pre-line text-sm">{detail.decision_notes}</p>
            </div>
          ) : null}

          {canDecide && allowed.length > 0 ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                {form.data?.entrance_test_enabled ? (
                  <Field label={t("admissions.entrance_test.score")}>
                    <Input
                      type="number"
                      min={0}
                      max={detail.test_max_score || undefined}
                      data-testid="admission-decision-score"
                      value={score}
                      disabled={busy !== null}
                      onChange={(event) => setScore(event.target.value)}
                    />
                  </Field>
                ) : null}
                <Field label={t("admissions.decision_notes")}>
                  <Input
                    data-testid="admission-decision-notes"
                    value={decisionNotes}
                    disabled={busy !== null}
                    onChange={(event) => setDecisionNotes(event.target.value)}
                  />
                </Field>
              </div>
              <div className="flex flex-wrap gap-2">
                {allowed.map((status) => (
                  <Button
                    key={status}
                    variant={status === "rejected" ? "destructive" : status === "accepted" ? "primary" : "outline"}
                    disabled={busy !== null}
                    data-testid={`admission-decide-${status}`}
                    onClick={() => void decide(status)}
                  >
                    {busy === status ? t("admissions.decision.saving") : t(DECISION_KEY[status])}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {detail.status === "accepted" && !detail.student_id ? (
        <Card>
          <CardContent className="space-y-3 p-4" data-testid="admission-conversion">
            <h2 className="text-sm font-semibold">{t("admissions.conversion.title")}</h2>
            <p className="text-sm text-muted-foreground">{t("admissions.conversion.hint")}</p>
            {conversion.isPending ? (
              <p className="text-sm text-muted-foreground" role="status">
                {t("common.loading")}
              </p>
            ) : conversion.isError || !conversion.data ? (
              <p className="text-sm text-destructive">{t("admissions.load_error")}</p>
            ) : (
              <ConversionSummary preview={conversion.data} />
            )}
            {canDecide ? (
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-input"
                    data-testid="admission-create-accounts"
                    checked={createAccounts}
                    disabled={busy !== null}
                    onChange={(event) => setCreateAccounts(event.target.checked)}
                  />
                  {t("admissions.conversion.create_accounts")}
                </label>
                <Button
                  data-testid="admission-convert"
                  disabled={busy !== null || conversion.data?.can_convert === false}
                  onClick={() => void convert()}
                >
                  {busy === "convert"
                    ? t("admissions.conversion.saving")
                    : t("admissions.conversion.action")}
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {converted ? (
        <Card>
          <CardContent className="space-y-2 p-4" role="status" data-testid="admission-converted">
            <p className="text-sm text-primary">
              {t("admissions.conversion.done", { name: detail.person.full_name })}
            </p>
            <p className="text-sm">
              {t("admissions.student_number")}: {converted.student_number} ·{" "}
              <Link className="ui-link" to={`/students/${converted.student_id}`}>
                {t("admissions.student")}
              </Link>
            </p>
            {converted.warnings.map((warning) => (
              <p key={warning} className="text-sm text-muted-foreground">
                {t(`admissions.warning.${warning}`)}
              </p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-destructive" data-testid="admission-profile-action-error">
          {error}
        </p>
      ) : null}

      <Card>
        <CardContent className="space-y-3 p-4">
          <h2 className="text-sm font-semibold">{t("admissions.documents")}</h2>
          <ApplicationDocuments application={detail} canManage={canManage} />
        </CardContent>
      </Card>
    </Page>
  );
}

function ConversionSummary({ preview }: { preview: ConversionPreview }) {
  const { t } = useI18n();
  if (!preview.can_convert) {
    return (
      <p className="text-sm text-destructive" data-testid="admission-conversion-blocked">
        {preview.reason === "already_converted"
          ? t("admissions.conversion.already")
          : t("admissions.conversion.not_ready")}
      </p>
    );
  }
  return (
    <div className="space-y-2" data-testid="admission-conversion-preview">
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Row label={t("admissions.student_number")} value={preview.student_number} />
        <Row label={t("admissions.year")} value={preview.year_code} />
        <Row
          label={t("admissions.level")}
          value={[preview.level_code, preview.section_code].filter(Boolean).join(" · ")}
        />
        <Row label={t("admissions.guardians")} value={String(preview.guardian_count)} />
      </dl>
      {preview.section_source === "auto" ? (
        <p className="text-sm text-muted-foreground">{t("admissions.section.auto")}</p>
      ) : null}
      {preview.warnings.map((warning) => (
        <p key={warning} className="text-sm text-muted-foreground">
          {t(`admissions.warning.${warning}`)}
        </p>
      ))}
      {preview.accounts.length > 0 ? (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">{t("admissions.conversion.accounts")}</p>
          <ul className="space-y-1 text-sm">
            {preview.accounts.map((account) => (
              <li key={account.person_id}>
                {account.name} · {t(`admissions.conversion.account.${account.action}`)}
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">{t("admissions.conversion.accounts.hint")}</p>
        </div>
      ) : null}
    </div>
  );
}
