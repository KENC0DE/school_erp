import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Dialog, EmptyState, Field, Input, Select } from "@erp/ui-web";
import { useState, type FormEvent } from "react";

import { EMPTY_NAME, NameFields, type NameValue } from "../../components/NameFields";
import { api } from "../../lib/api";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { STUDENTS, hasPermission, withQuery } from "./queries";
import type { Guardian, PersonSearchList, StudentDetail } from "./types";

const RELATIONSHIPS = ["mother", "father", "guardian", "grandparent", "sibling", "other"] as const;

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function StudentGuardians({
  student,
  canManage,
}: {
  student: StudentDetail;
  canManage: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [names, setNames] = useState<NameValue>({ ...EMPTY_NAME });
  const [relationship, setRelationship] = useState("guardian");
  const [primary, setPrimary] = useState(false);
  const [pickup, setPickup] = useState(true);
  const [search, setSearch] = useState("");
  const [submittedSearch, setSubmittedSearch] = useState("");
  const [personId, setPersonId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const canSearchPeople = hasPermission(user?.permissions, "people.view");

  const people = useQuery({
    queryKey: ["people", "search", submittedSearch],
    queryFn: () => api.get<PersonSearchList>(withQuery("/api/v1/people/search", { q: submittedSearch })),
    enabled: mode === "existing" && canSearchPeople && submittedSearch.length > 0,
    retry: false,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["students", "detail", student.id] });
    void queryClient.invalidateQueries({ queryKey: ["students", "list"] });
  };

  const add = useMutation({
    mutationFn: () => {
      const body =
        mode === "existing"
          ? {
              person_id: personId,
              relationship,
              is_primary: primary,
              can_pickup: pickup,
            }
          : {
              person: Object.fromEntries(
                Object.entries(names).map(([key, value]) => [key, clean(value)]),
              ),
              relationship,
              is_primary: primary,
              can_pickup: pickup,
            };
      return api.post<Guardian>(`${STUDENTS}/${student.id}/guardians`, body);
    },
    onSuccess: () => {
      setAdding(false);
      setNames({ ...EMPTY_NAME });
      setPersonId("");
      setSearch("");
      setSubmittedSearch("");
      setError(null);
      refresh();
    },
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("students.guardian.failed"));
    },
  });

  const remove = useMutation({
    mutationFn: (guardianId: string) =>
      api.del(`${STUDENTS}/${student.id}/guardians/${guardianId}`),
    onSuccess: refresh,
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("students.guardian.failed"));
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    add.mutate();
  }

  const canSubmit = mode === "existing" ? Boolean(personId) : Boolean(clean(names.given_name_en));

  return (
    <div className="space-y-4" data-testid="student-guardians">
      {canManage ? (
        <Button onClick={() => setAdding(true)}>{t("students.guardian.add")}</Button>
      ) : null}

      {student.guardians.length === 0 ? (
        <EmptyState title={t("students.guardian.empty")} />
      ) : (
        <ul className="space-y-2">
          {student.guardians.map((guardian) => (
            <li
              key={guardian.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
              data-testid={`guardian-${guardian.id}`}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium">{guardian.person.full_name}</p>
                <p className="text-xs text-muted-foreground">
                  {t(`students.relationship.${guardian.relationship}`)}
                  {guardian.is_primary ? ` · ${t("students.guardian.primary")}` : ""}
                  {guardian.can_pickup ? ` · ${t("students.guardian.can_pickup")}` : ""}
                </p>
              </div>
              {canManage ? (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(guardian.id)}
                >
                  {t("students.guardian.remove")}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <Dialog
        open={adding}
        onClose={() => setAdding(false)}
        title={t("students.guardian.add")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAdding(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              form="guardian-add-form"
              disabled={!canSubmit || add.isPending}
            >
              {add.isPending ? t("students.guardian.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        <form id="guardian-add-form" className="space-y-4" onSubmit={submit}>
          {canSearchPeople ? (
            <div className="flex gap-2">
              <Button
                type="button"
                variant={mode === "new" ? "primary" : "outline"}
                onClick={() => setMode("new")}
              >
                {t("students.guardian.new_person")}
              </Button>
              <Button
                type="button"
                variant={mode === "existing" ? "primary" : "outline"}
                onClick={() => setMode("existing")}
              >
                {t("students.guardian.existing_person")}
              </Button>
            </div>
          ) : null}

          {mode === "existing" ? (
            <div className="space-y-2">
              <div className="flex items-end gap-2">
                <Field label={t("students.guardian.search")} className="flex-1">
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder={t("students.guardian.search_placeholder")}
                  />
                </Field>
                <Button
                  type="button"
                  variant="outline"
                  disabled={!search.trim()}
                  onClick={() => setSubmittedSearch(search.trim())}
                >
                  {t("students.search.action")}
                </Button>
              </div>
              <Select
                aria-label={t("students.guardian.search")}
                value={personId}
                onChange={(event) => setPersonId(event.target.value)}
              >
                <option value="">{t("students.guardian.choose_person")}</option>
                {(people.data?.items ?? []).map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.full_name}
                  </option>
                ))}
              </Select>
              {people.isFetching ? (
                <p className="text-xs text-muted-foreground">{t("students.guardian.searching")}</p>
              ) : null}
            </div>
          ) : (
            <NameFields value={names} onChange={setNames} />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("students.guardian.relationship")}>
              <Select value={relationship} onChange={(event) => setRelationship(event.target.value)}>
                {RELATIONSHIPS.map((item) => (
                  <option key={item} value={item}>
                    {t(`students.relationship.${item}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex flex-col gap-2 pt-6 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={primary} onChange={(event) => setPrimary(event.target.checked)} />
                {t("students.guardian.primary")}
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={pickup} onChange={(event) => setPickup(event.target.checked)} />
                {t("students.guardian.can_pickup")}
              </label>
            </div>
          </div>
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
        </form>
      </Dialog>
    </div>
  );
}
