import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { EmptyState, ErrorState, LoadingState } from "@erp/ui-web";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { ACADEMICS, useProfiles, useYears } from "./queries";
import type { CurriculumApplyResult, CurriculumProfile } from "./types";

const EMPTY_EDIT = { name: "", name_am: "", description: "", term_system: "semester" };

function profileBadge(profile: CurriculumProfile, t: (key: string) => string): string {
  if (profile.is_starter && !profile.is_verified) return t("academics.curriculum.unverified");
  if (profile.is_verified) return t("academics.curriculum.verified");
  return t("academics.curriculum.starter");
}

export function CurriculumPanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const profiles = useProfiles();
  const years = useYears();
  const [selectedId, setSelectedId] = useState("");
  const [edit, setEdit] = useState(EMPTY_EDIT);
  const [duplicate, setDuplicate] = useState({ code: "", name: "" });
  const [applyYear, setApplyYear] = useState("");
  const [preview, setPreview] = useState<CurriculumApplyResult | null>(null);

  const rows = profiles.data?.items ?? [];
  const selected = rows.find((profile) => profile.id === selectedId) ?? rows[0] ?? null;

  useEffect(() => {
    if (!selectedId && rows[0]) setSelectedId(rows[0].id);
  }, [rows, selectedId]);

  useEffect(() => {
    if (!selected) return;
    setEdit({
      name: selected.name,
      name_am: selected.name_am ?? "",
      description: selected.description ?? "",
      term_system: selected.term_system,
    });
    setPreview(null);
  }, [selected?.id, selected?.row_version]);

  useEffect(() => {
    if (applyYear || !years.data) return;
    setApplyYear(years.data.current_year_id ?? years.data.items[0]?.id ?? "");
  }, [applyYear, years.data]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["academics"] });

  const save = useMutation({
    mutationFn: () =>
      api.patch(`${ACADEMICS}/curriculum-profiles/${selected?.id}`, {
        ...edit,
        name_am: edit.name_am || null,
        description: edit.description || null,
        row_version: selected?.row_version,
      }),
    onSuccess: () => void refresh(),
  });

  const duplicateProfile = useMutation({
    mutationFn: () =>
      api.post(`${ACADEMICS}/curriculum-profiles/${selected?.id}/duplicate`, {
        code: duplicate.code,
        name: duplicate.name,
      }),
    onSuccess: (created) => {
      const result = created as CurriculumProfile;
      setDuplicate({ code: "", name: "" });
      setSelectedId(result.id);
      void refresh();
    },
  });

  const runApply = useMutation({
    mutationFn: (confirm: boolean) =>
      api.post<CurriculumApplyResult>(`${ACADEMICS}/curriculum-profiles/${selected?.id}/apply`, {
        year_id: applyYear,
        confirm,
      }),
    onSuccess: (result) => {
      setPreview(result);
      if (result.applied) void refresh();
    },
  });

  const error =
    save.error instanceof ApiRequestError
      ? save.error.message
      : duplicateProfile.error instanceof ApiRequestError
        ? duplicateProfile.error.message
        : runApply.error instanceof ApiRequestError
          ? runApply.error.message
          : null;

  if (profiles.isLoading) return <LoadingState label={t("common.loading")} />;
  if (profiles.isError)
    return (
      <ErrorState
        title={t("common.error")}
        requestId={requestIdOf(profiles.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button size="sm" variant="outline" onClick={() => void profiles.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <Card>
        <CardHeader>
          <CardTitle>{t("academics.curriculum.title")}</CardTitle>
          <CardDescription>{t("academics.curriculum.starter_warning")}</CardDescription>
        </CardHeader>
        <CardContent>
          {rows.length === 0 ? <EmptyState title={t("academics.empty.profiles")} /> : null}
          <ul className="space-y-2">
            {rows.map((profile) => (
              <li key={profile.id}>
                <button
                  type="button"
                  data-testid={`profile-${profile.code}`}
                  aria-pressed={profile.id === selected?.id}
                  className={`w-full rounded-md border px-3 py-2 text-start text-sm transition ${
                    profile.id === selected?.id
                      ? "border-ring bg-muted font-medium"
                      : "border-border hover:bg-muted"
                  }`}
                  onClick={() => setSelectedId(profile.id)}
                >
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <span>{profile.name}</span>
                    <Badge>{profileBadge(profile, t)}</Badge>
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {t(`academics.term_system.${profile.term_system}`)} ·{" "}
                    {profile.in_use ? t("academics.curriculum.in_use") : t("academics.curriculum.not_in_use")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {selected ? (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{selected.name}</CardTitle>
              <CardDescription>{selected.description ?? t("academics.curriculum.select_hint")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {canManage ? (
                <form
                  className="grid gap-3 sm:grid-cols-2"
                  onSubmit={(event: FormEvent) => {
                    event.preventDefault();
                    save.mutate();
                  }}
                >
                  <Input
                    aria-label={t("academics.curriculum.name")}
                    data-testid="profile-name"
                    placeholder={t("academics.curriculum.name")}
                    value={edit.name}
                    required
                    onChange={(event) => setEdit((d) => ({ ...d, name: event.target.value }))}
                  />
                  <Input
                    aria-label={t("academics.curriculum.name_am")}
                    data-testid="profile-name-am"
                    placeholder={t("academics.curriculum.name_am")}
                    value={edit.name_am}
                    onChange={(event) => setEdit((d) => ({ ...d, name_am: event.target.value }))}
                  />
                  <Input
                    aria-label={t("academics.curriculum.description")}
                    data-testid="profile-description"
                    placeholder={t("academics.curriculum.description")}
                    value={edit.description}
                    maxLength={500}
                    onChange={(event) => setEdit((d) => ({ ...d, description: event.target.value }))}
                  />
                  <select
                    aria-label={t("academics.year.term_system")}
                    data-testid="profile-term-system"
                    className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={edit.term_system}
                    onChange={(event) => setEdit((d) => ({ ...d, term_system: event.target.value }))}
                  >
                    <option value="semester">{t("academics.term_system.semester")}</option>
                    <option value="quarter">{t("academics.term_system.quarter")}</option>
                  </select>
                  <div className="sm:col-span-2">
                    <Button type="submit" disabled={save.isPending}>
                      {save.isPending ? t("academics.curriculum.saving") : t("academics.curriculum.save")}
                    </Button>
                  </div>
                </form>
              ) : null}

              <div>
                <h4 className="mb-2 text-sm font-semibold">{t("academics.curriculum.levels")}</h4>
                {selected.levels.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t("academics.curriculum.no_levels")}</p>
                ) : (
                  <ul className="grid gap-2 text-sm sm:grid-cols-2">
                    {selected.levels.map((level) => (
                      <li key={level.level_id} className="rounded border border-border px-3 py-2">
                        <p className="font-medium">{level.level_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {level.subjects.map((subject) => subject.name).join(", ")}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {canManage ? (
                <form
                  className="grid gap-3 rounded-md border border-border p-3 sm:grid-cols-3"
                  onSubmit={(event: FormEvent) => {
                    event.preventDefault();
                    duplicateProfile.mutate();
                  }}
                >
                  <p className="text-sm font-medium sm:col-span-3">{t("academics.curriculum.duplicate_hint")}</p>
                  <Input
                    aria-label={t("academics.curriculum.duplicate_code")}
                    data-testid="profile-duplicate-code"
                    placeholder={t("academics.curriculum.duplicate_code")}
                    value={duplicate.code}
                    required
                    onChange={(event) => setDuplicate((d) => ({ ...d, code: event.target.value }))}
                  />
                  <Input
                    aria-label={t("academics.curriculum.duplicate_name")}
                    data-testid="profile-duplicate-name"
                    placeholder={t("academics.curriculum.duplicate_name")}
                    value={duplicate.name}
                    required
                    onChange={(event) => setDuplicate((d) => ({ ...d, name: event.target.value }))}
                  />
                  <Button type="submit" disabled={duplicateProfile.isPending}>
                    {duplicateProfile.isPending
                      ? t("academics.curriculum.duplicating")
                      : t("academics.curriculum.duplicate")}
                  </Button>
                </form>
              ) : null}

              {error ? (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("academics.curriculum.apply_title")}</CardTitle>
              <CardDescription>{t("academics.curriculum.apply_hint")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <select
                aria-label={t("academics.curriculum.apply_year")}
                data-testid="profile-apply-year"
                className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={applyYear}
                onChange={(event) => {
                  setApplyYear(event.target.value);
                  setPreview(null);
                }}
              >
                <option value="">{t("academics.curriculum.apply_year")}</option>
                {(years.data?.items ?? []).map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name} · {t(`academics.term_system.${year.term_system}`)}
                  </option>
                ))}
              </select>
              {canManage ? (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    data-testid="profile-preview"
                    disabled={!applyYear || runApply.isPending}
                    onClick={() => runApply.mutate(false)}
                  >
                    {runApply.isPending ? t("academics.curriculum.previewing") : t("academics.curriculum.preview")}
                  </Button>
                  <Button
                    data-testid="profile-apply"
                    disabled={
                      !preview ||
                      preview.applied ||
                      !preview.term_system_matches ||
                      runApply.isPending
                    }
                    onClick={() => runApply.mutate(true)}
                  >
                    {runApply.isPending ? t("academics.curriculum.applying") : t("academics.curriculum.apply")}
                  </Button>
                </div>
              ) : null}
              {preview ? (
                <div data-testid="profile-preview-result" className="rounded border border-border p-3 text-sm">
                  <p className={preview.term_system_matches ? "" : "text-destructive"}>
                    {preview.term_system_matches
                      ? t("academics.curriculum.term_match")
                      : t("academics.curriculum.term_mismatch")}
                  </p>
                  <p>{t("academics.curriculum.changes", { count: preview.levels_changed })}</p>
                  <p>
                    +{preview.assignments_added} / −{preview.assignments_removed} ·{" "}
                    {t("academics.curriculum.credits_changed")}: {preview.credits_changed}
                  </p>
                  {preview.changed_levels.length > 0 ? (
                    <p className="text-xs text-muted-foreground">{preview.changed_levels.join(", ")}</p>
                  ) : null}
                  {preview.applied ? <Badge>{t("academics.curriculum.applied")}</Badge> : null}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
