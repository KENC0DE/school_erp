import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { ACADEMICS, useGroups, useLevels, useLevelSubjects, useSubjects } from "./queries";

interface Assignment {
  credit: number;
}

export function SubjectsPanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const subjects = useSubjects();
  const groups = useGroups();
  const levels = useLevels(canManage);
  const [levelId, setLevelId] = useState("");
  const assignments = useLevelSubjects(levelId || null);
  const [assigned, setAssigned] = useState<Record<string, Assignment>>({});
  const [subjectDraft, setSubjectDraft] = useState({ code: "", name: "", name_am: "" });
  const [groupDraft, setGroupDraft] = useState({ code: "", name: "", subject_ids: [] as string[] });

  useEffect(() => {
    const rows = assignments.data?.items ?? [];
    setAssigned(
      Object.fromEntries(rows.map((item) => [item.subject_id, { credit: item.credit }])),
    );
  }, [assignments.data]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["academics"] });

  const createSubject = useMutation({
    mutationFn: () =>
      api.post(`${ACADEMICS}/subjects`, {
        code: subjectDraft.code,
        name: subjectDraft.name,
        name_am: subjectDraft.name_am || null,
      }),
    onSuccess: () => {
      setSubjectDraft({ code: "", name: "", name_am: "" });
      void refresh();
    },
  });

  const saveAssignments = useMutation({
    mutationFn: () =>
      api.put(`${ACADEMICS}/levels/${levelId}/subjects`, {
        subjects: Object.entries(assigned).map(([subjectId, value]) => ({
          subject_id: subjectId,
          credit: value.credit,
        })),
      }),
    onSuccess: () => void refresh(),
  });

  const createGroup = useMutation({
    mutationFn: () =>
      api.post(`${ACADEMICS}/subject-groups`, {
        code: groupDraft.code,
        name: groupDraft.name,
        subject_ids: groupDraft.subject_ids,
      }),
    onSuccess: () => {
      setGroupDraft({ code: "", name: "", subject_ids: [] });
      void refresh();
    },
  });

  const error =
    createSubject.error instanceof ApiRequestError
      ? createSubject.error.message
      : saveAssignments.error instanceof ApiRequestError
        ? saveAssignments.error.message
        : createGroup.error instanceof ApiRequestError
          ? createGroup.error.message
          : null;

  const subjectRows = subjects.data?.items ?? [];
  const levelRows = levels.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("academics.subject.create_title")}</CardTitle>
            <CardDescription>{t("academics.subject.create_hint")}</CardDescription>
          </CardHeader>
          <CardContent>
            {canManage ? (
              <form
                className="grid gap-3 sm:grid-cols-3"
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  createSubject.mutate();
                }}
              >
                <Input
                  aria-label={t("academics.subject.code")}
                  data-testid="subject-code"
                  placeholder={t("academics.subject.code")}
                  value={subjectDraft.code}
                  required
                  onChange={(event) => setSubjectDraft((d) => ({ ...d, code: event.target.value }))}
                />
                <Input
                  aria-label={t("academics.subject.name")}
                  data-testid="subject-name"
                  placeholder={t("academics.subject.name")}
                  value={subjectDraft.name}
                  required
                  onChange={(event) => setSubjectDraft((d) => ({ ...d, name: event.target.value }))}
                />
                <Input
                  aria-label={t("academics.subject.name_am")}
                  data-testid="subject-name-am"
                  placeholder={t("academics.subject.name_am")}
                  value={subjectDraft.name_am}
                  onChange={(event) => setSubjectDraft((d) => ({ ...d, name_am: event.target.value }))}
                />
                <div className="sm:col-span-3">
                  <Button type="submit" disabled={createSubject.isPending}>
                    {createSubject.isPending ? t("academics.subject.creating") : t("academics.subject.create")}
                  </Button>
                </div>
              </form>
            ) : null}
            <ul className="mt-4 divide-y divide-border text-sm">
              {subjectRows.map((subject) => (
                <li key={subject.id} className="flex items-center justify-between gap-2 py-2">
                  <span>
                    <span className="font-medium">{subject.name}</span>{" "}
                    <span className="text-xs text-muted-foreground">
                      {subject.code} · {subject.name_am}
                    </span>
                  </span>
                  <Badge>{t(subject.is_active ? "common.enabled" : "common.disabled")}</Badge>
                </li>
              ))}
              {subjectRows.length === 0 ? (
                <li className="py-2 text-muted-foreground">{t("academics.empty.subjects")}</li>
              ) : null}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("academics.subject.assign_title")}</CardTitle>
            <CardDescription>{t("academics.subject.assign_hint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <select
              aria-label={t("academics.subject.select_level")}
              data-testid="subject-level"
              className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={levelId}
              onChange={(event) => setLevelId(event.target.value)}
            >
              <option value="">{t("academics.subject.select_level")}</option>
              {levelRows.map((level) => (
                <option key={level.id} value={level.id}>
                  {level.name}
                </option>
              ))}
            </select>
            {levelId ? (
              assignments.isLoading ? (
                <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
              ) : (
                <ul className="max-h-72 space-y-1 overflow-y-auto text-sm">
                  {subjectRows.map((subject) => {
                    const checked = Boolean(assigned[subject.id]);
                    return (
                      <li key={subject.id} className="flex items-center justify-between gap-2 py-1">
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            data-testid={`assign-${subject.code}`}
                            checked={checked}
                            disabled={!canManage}
                            onChange={(event) =>
                              setAssigned((current) => {
                                const next = { ...current };
                                if (event.target.checked) next[subject.id] = { credit: 1 };
                                else delete next[subject.id];
                                return next;
                              })
                            }
                          />
                          <span>{subject.name}</span>
                        </label>
                        <label className="flex items-center gap-1 text-xs text-muted-foreground">
                          {t("academics.subject.credit")}
                          <Input
                            type="number"
                            aria-label={`${t("academics.subject.credit")} ${subject.name}`}
                            className="h-8 w-16"
                            min={0}
                            max={100}
                            disabled={!checked || !canManage}
                            value={assigned[subject.id]?.credit ?? 1}
                            onChange={(event) =>
                              setAssigned((current) => ({
                                ...current,
                                [subject.id]: { credit: Number(event.target.value) },
                              }))
                            }
                          />
                        </label>
                      </li>
                    );
                  })}
                </ul>
              )
            ) : (
              <p className="text-sm text-muted-foreground">{t("academics.subject.choose_level")}</p>
            )}
            {canManage && levelId ? (
              <Button onClick={() => saveAssignments.mutate()} disabled={saveAssignments.isPending}>
                {saveAssignments.isPending
                  ? t("academics.subject.assign_saving")
                  : t("academics.subject.assign_save")}
              </Button>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("academics.subject_groups")}</CardTitle>
          <CardDescription>{t("academics.subject.group_hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {canManage ? (
            <form
              className="grid gap-3 sm:grid-cols-3"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                createGroup.mutate();
              }}
            >
              <Input
                aria-label={t("academics.subject.group_code")}
                data-testid="group-code"
                placeholder={t("academics.subject.group_code")}
                value={groupDraft.code}
                required
                onChange={(event) => setGroupDraft((d) => ({ ...d, code: event.target.value }))}
              />
              <Input
                aria-label={t("academics.subject_group.name")}
                data-testid="group-name"
                placeholder={t("academics.subject_group.name")}
                value={groupDraft.name}
                required
                onChange={(event) => setGroupDraft((d) => ({ ...d, name: event.target.value }))}
              />
              <Button type="submit" disabled={createGroup.isPending}>
                {createGroup.isPending ? t("academics.subject.group_creating") : t("academics.subject.group_create")}
              </Button>
              <fieldset className="sm:col-span-3">
                <legend className="mb-1 text-sm font-medium">{t("academics.subject_group.members")}</legend>
                <div className="flex flex-wrap gap-3 text-sm">
                  {subjectRows.map((subject) => (
                    <label key={subject.id} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={groupDraft.subject_ids.includes(subject.id)}
                        onChange={(event) =>
                          setGroupDraft((d) => ({
                            ...d,
                            subject_ids: event.target.checked
                              ? [...d.subject_ids, subject.id]
                              : d.subject_ids.filter((id) => id !== subject.id),
                          }))
                        }
                      />
                      {subject.name}
                    </label>
                  ))}
                </div>
              </fieldset>
            </form>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
          <ul className="divide-y divide-border text-sm">
            {(groups.data?.items ?? []).map((group) => (
              <li key={group.id} className="py-2">
                <span className="font-medium">{group.name}</span>{" "}
                <span className="text-xs text-muted-foreground">
                  {group.subjects.map((subject) => subject.name).join(", ")}
                </span>
              </li>
            ))}
            {(groups.data?.items ?? []).length === 0 ? (
              <li className="py-2 text-muted-foreground">{t("academics.empty.subject_groups")}</li>
            ) : null}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
