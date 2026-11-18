import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { api } from "../../lib/api";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { ACADEMICS, can, useHomeroomUsers, useLevels, useSections, useYears } from "./queries";

const EMPTY = { level_id: "", code: "", name: "", name_am: "", capacity: "40", homeroom_user_id: "" };

export function SectionsPanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const years = useYears();
  const levels = useLevels(canManage);
  const [yearId, setYearId] = useState("");
  const sections = useSections(yearId || null);
  const usersAllowed = can(user?.permissions ?? [], "users.view");
  const homeroomUsers = useHomeroomUsers(canManage && usersAllowed);
  const [draft, setDraft] = useState(EMPTY);

  useEffect(() => {
    if (yearId || !years.data) return;
    setYearId(years.data.current_year_id ?? years.data.items[0]?.id ?? "");
  }, [yearId, years.data]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["academics"] });

  const create = useMutation({
    mutationFn: () =>
      api.post(`${ACADEMICS}/sections`, {
        year_id: yearId,
        level_id: draft.level_id,
        code: draft.code,
        name: draft.name || null,
        name_am: draft.name_am || null,
        capacity: Number(draft.capacity),
        homeroom_user_id: draft.homeroom_user_id || null,
      }),
    onSuccess: () => {
      setDraft(EMPTY);
      void refresh();
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.del(`${ACADEMICS}/sections/${id}`),
    onSuccess: () => void refresh(),
  });

  const error =
    create.error instanceof ApiRequestError
      ? create.error.message
      : remove.error instanceof ApiRequestError
        ? remove.error.message
        : null;
  const rows = sections.data?.items ?? [];
  const levelRows = levels.data?.items ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("academics.section.create_title")}</CardTitle>
          <CardDescription>{t("academics.section.create_hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="block max-w-xs space-y-1 text-sm">
            <span className="font-medium">{t("academics.section.year")}</span>
            <select
              aria-label={t("academics.section.year")}
              data-testid="section-year"
              className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={yearId}
              onChange={(event) => setYearId(event.target.value)}
            >
              <option value="">{t("academics.section.year")}</option>
              {(years.data?.items ?? []).map((year) => (
                <option key={year.id} value={year.id}>
                  {year.name}
                </option>
              ))}
            </select>
          </label>

          {canManage ? (
            <form
              className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                create.mutate();
              }}
            >
              <label className="space-y-1 text-sm">
                <span className="font-medium">{t("academics.section.level")}</span>
                <select
                  aria-label={t("academics.section.level")}
                  data-testid="section-level"
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={draft.level_id}
                  required
                  onChange={(event) => setDraft((d) => ({ ...d, level_id: event.target.value }))}
                >
                  <option value="">{t("academics.section.level")}</option>
                  {levelRows.map((level) => (
                    <option key={level.id} value={level.id}>
                      {level.name}
                    </option>
                  ))}
                </select>
              </label>
              <Input
                aria-label={t("academics.section.code")}
                data-testid="section-code"
                placeholder={t("academics.section.code")}
                value={draft.code}
                required
                onChange={(event) => setDraft((d) => ({ ...d, code: event.target.value }))}
              />
              <Input
                aria-label={t("academics.section.name")}
                data-testid="section-name"
                placeholder={t("academics.section.name")}
                value={draft.name}
                onChange={(event) => setDraft((d) => ({ ...d, name: event.target.value }))}
              />
              <Input
                aria-label={t("academics.section.name_am")}
                data-testid="section-name-am"
                placeholder={t("academics.section.name_am")}
                value={draft.name_am}
                onChange={(event) => setDraft((d) => ({ ...d, name_am: event.target.value }))}
              />
              <Input
                aria-label={t("academics.section.capacity")}
                data-testid="section-capacity"
                type="number"
                min={1}
                max={500}
                placeholder={t("academics.section.capacity")}
                value={draft.capacity}
                onChange={(event) => setDraft((d) => ({ ...d, capacity: event.target.value }))}
              />
              {homeroomUsers.data ? (
                <label className="space-y-1 text-sm">
                  <span className="font-medium">{t("academics.section.homeroom")}</span>
                  <select
                    aria-label={t("academics.section.homeroom")}
                    data-testid="section-homeroom"
                    className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                    value={draft.homeroom_user_id}
                    onChange={(event) => setDraft((d) => ({ ...d, homeroom_user_id: event.target.value }))}
                  >
                    <option value="">{t("academics.section.homeroom_none")}</option>
                    {homeroomUsers.data.items
                      .filter((item) => item.is_active)
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.display_name}
                        </option>
                      ))}
                  </select>
                </label>
              ) : null}
              <div className="sm:col-span-2 lg:col-span-3">
                <Button type="submit" disabled={create.isPending || !yearId}>
                  {create.isPending ? t("academics.section.creating") : t("academics.section.create")}
                </Button>
              </div>
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
          <CardTitle>{t("academics.sections")}</CardTitle>
          <CardDescription>{t("academics.section.list_hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          {sections.isLoading ? <p className="text-sm text-muted-foreground">{t("common.loading")}</p> : null}
          {rows.length === 0 && !sections.isLoading ? (
            <p className="text-sm text-muted-foreground">{t("academics.empty.sections")}</p>
          ) : null}
          <ul className="divide-y divide-border text-sm">
            {rows.map((section) => (
              <li key={section.id} data-testid={`section-row-${section.code}`} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <span>
                  <span className="font-medium">
                    {section.level_name} · {section.code}
                  </span>{" "}
                  <span className="text-xs text-muted-foreground">
                    {section.name ?? ""} · {t("academics.section.capacity")}: {section.capacity}
                    {section.homeroom_name ? ` · ${section.homeroom_name}` : ""}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <Badge>{t(section.is_active ? "common.enabled" : "common.disabled")}</Badge>
                  {canManage ? (
                    <Button variant="ghost" onClick={() => remove.mutate(section.id)}>
                      {t("academics.section.delete")}
                    </Button>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
