import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { ACADEMICS, useProfiles, useYears } from "./queries";
import type { Year } from "./types";

const EMPTY = {
  code: "",
  name: "",
  name_am: "",
  start_date: "",
  end_date: "",
  curriculum_profile_id: "",
};

function statusLabel(t: (key: string) => string, status: Year["status"]): string {
  return t(`academics.year.${status}`);
}

export function YearsPanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const years = useYears();
  const profiles = useProfiles();
  const [draft, setDraft] = useState(EMPTY);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["academics"] });

  const create = useMutation({
    mutationFn: () =>
      api.post(`${ACADEMICS}/academic-years`, {
        code: draft.code,
        name: draft.name,
        name_am: draft.name_am || null,
        start_date: draft.start_date,
        end_date: draft.end_date,
        curriculum_profile_id: draft.curriculum_profile_id || null,
      }),
    onSuccess: () => {
      setDraft(EMPTY);
      void refresh();
    },
  });

  const transition = useMutation({
    mutationFn: ({ path }: { path: string }) => api.post(path),
    onSuccess: () => void refresh(),
  });

  function update(key: keyof typeof EMPTY, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  const error = create.error instanceof ApiRequestError ? create.error.message : null;
  const rows = years.data?.items ?? [];
  const options = profiles.data?.items ?? [];
  const selectedProfile = options.find((profile) => profile.id === draft.curriculum_profile_id);

  return (
    <div className="space-y-4">
      {canManage ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("academics.year.create_title")}</CardTitle>
            <CardDescription>{t("academics.year.create_hint")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" onSubmit={submit}>
              <Input
                aria-label={t("academics.year.code")}
                data-testid="year-code"
                placeholder={t("academics.year.code")}
                value={draft.code}
                required
                onChange={(event) => update("code", event.target.value)}
              />
              <Input
                aria-label={t("academics.year.name")}
                data-testid="year-name"
                placeholder={t("academics.year.name")}
                value={draft.name}
                required
                onChange={(event) => update("name", event.target.value)}
              />
              <Input
                aria-label={t("academics.year.name_am")}
                data-testid="year-name-am"
                placeholder={t("academics.year.name_am")}
                value={draft.name_am}
                onChange={(event) => update("name_am", event.target.value)}
              />
              <label className="space-y-1 text-sm">
                <span className="font-medium">{t("academics.year.start_date")}</span>
                <Input
                  aria-label={t("academics.year.start_date")}
                  data-testid="year-start"
                  type="date"
                  value={draft.start_date}
                  required
                  onChange={(event) => update("start_date", event.target.value)}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium">{t("academics.year.end_date")}</span>
                <Input
                  aria-label={t("academics.year.end_date")}
                  data-testid="year-end"
                  type="date"
                  value={draft.end_date}
                  required
                  onChange={(event) => update("end_date", event.target.value)}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium">{t("academics.year.profile")}</span>
                <select
                  aria-label={t("academics.year.profile")}
                  data-testid="year-profile"
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={draft.curriculum_profile_id}
                  onChange={(event) => update("curriculum_profile_id", event.target.value)}
                >
                  <option value="">{t("academics.year.no_profile")}</option>
                  {options.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </label>
              {selectedProfile ? (
                <p className="text-xs text-muted-foreground sm:col-span-2 lg:col-span-3">
                  {t("academics.year.profile_hint", {
                    term_system: t(`academics.term_system.${selectedProfile.term_system}`),
                  })}
                </p>
              ) : null}
              <div className="sm:col-span-2 lg:col-span-3">
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? t("academics.year.creating") : t("academics.year.create")}
                </Button>
              </div>
            </form>
            {error ? (
              <p role="alert" className="mt-3 text-sm text-destructive">
                {error}
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("academics.years")}</CardTitle>
          <CardDescription>{t("academics.year.list_hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          {years.isLoading ? <p className="text-sm text-muted-foreground">{t("common.loading")}</p> : null}
          {rows.length === 0 && !years.isLoading ? (
            <p className="text-sm text-muted-foreground">{t("academics.empty.years")}</p>
          ) : null}
          <ul className="space-y-4">
            {rows.map((year) => (
              <li key={year.id} data-testid={`year-row-${year.code}`} className="rounded-md border border-border p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold">
                      {year.name} <span className="text-xs text-muted-foreground">{year.code}</span>
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {year.start_date_display} — {year.end_date_display} ·{" "}
                      {t(`academics.term_system.${year.term_system}`)}
                      {year.curriculum_profile_code
                        ? ` · ${t("academics.year.profile")}: ${year.curriculum_profile_code}`
                        : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{statusLabel(t, year.status)}</Badge>
                    {year.id === years.data?.current_year_id ? <Badge>{t("academics.year.current")}</Badge> : null}
                    {canManage && year.status === "draft" ? (
                      <Button
                        variant="outline"
                        onClick={() =>
                          transition.mutate({ path: `${ACADEMICS}/academic-years/${year.id}/open` })
                        }
                      >
                        {t("academics.year.open_action")}
                      </Button>
                    ) : null}
                    {canManage && year.status === "open" ? (
                      <Button
                        variant="outline"
                        onClick={() =>
                          transition.mutate({ path: `${ACADEMICS}/academic-years/${year.id}/close` })
                        }
                      >
                        {t("academics.year.close_action")}
                      </Button>
                    ) : null}
                  </div>
                </div>
                <ul className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  {year.terms.map((term) => (
                    <li
                      key={term.id}
                      data-testid={`term-row-${year.code}-${term.number}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded border border-border px-3 py-2"
                    >
                      <span>
                        <span className="font-medium">{term.name}</span>{" "}
                        <span className="text-xs text-muted-foreground">
                          {term.start_date_display} — {term.end_date_display}
                        </span>
                        <Badge className="ms-2">{t(`academics.term.${term.status}`)}</Badge>
                      </span>
                      {canManage && year.status === "open" && term.status === "pending" ? (
                        <Button
                          variant="ghost"
                          onClick={() =>
                            transition.mutate({
                              path: `${ACADEMICS}/academic-years/${year.id}/terms/${term.id}/open`,
                            })
                          }
                        >
                          {t("academics.term.open_action")}
                        </Button>
                      ) : null}
                      {canManage && term.status === "open" ? (
                        <Button
                          variant="ghost"
                          onClick={() =>
                            transition.mutate({
                              path: `${ACADEMICS}/academic-years/${year.id}/terms/${term.id}/close`,
                            })
                          }
                        >
                          {t("academics.term.close_action")}
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
