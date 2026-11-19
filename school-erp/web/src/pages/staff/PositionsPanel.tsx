import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Checkbox,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Select,
  Textarea,
} from "@erp/ui-web";
import { useState, type FormEvent } from "react";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { STAFF, useDepartments, usePositions } from "./queries";
import type { Position } from "./types";

interface PositionForm {
  id: string | null;
  code: string;
  name: string;
  name_am: string;
  department_id: string;
  is_teaching: boolean;
  description: string;
  is_active: boolean;
  sort_order: string;
  row_version: number;
}

const EMPTY_FORM: PositionForm = {
  id: null,
  code: "",
  name: "",
  name_am: "",
  department_id: "",
  is_teaching: false,
  description: "",
  is_active: true,
  sort_order: "0",
  row_version: 0,
};

function formOf(position: Position): PositionForm {
  return {
    id: position.id,
    code: position.code,
    name: position.name,
    name_am: position.name_am ?? "",
    department_id: position.department_id ?? "",
    is_teaching: position.is_teaching,
    description: position.description ?? "",
    is_active: position.is_active,
    sort_order: String(position.sort_order),
    row_version: position.row_version,
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function PositionsPanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const positions = usePositions();
  const departments = useDepartments();
  const [form, setForm] = useState<PositionForm | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (data: PositionForm) => {
      const body = {
        code: data.code.trim(),
        name: data.name.trim(),
        name_am: clean(data.name_am),
        department_id: data.department_id || null,
        is_teaching: data.is_teaching,
        description: clean(data.description),
        is_active: data.is_active,
        sort_order: Number(data.sort_order || 0),
      };
      return data.id
        ? api.patch<Position>(`${STAFF}/positions/${data.id}`, {
            ...body,
            row_version: data.row_version,
          })
        : api.post<Position>(`${STAFF}/positions`, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "positions"] });
      setForm(null);
    },
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("staff.position.failed"));
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setError(null);
    save.mutate(form);
  }

  if (positions.isPending) {
    return <LoadingState label={t("common.loading")} testId="positions-loading" />;
  }
  if (positions.isError) {
    return (
      <ErrorState
        title={t("staff.load_error")}
        requestId={requestIdOf(positions.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button variant="outline" onClick={() => void positions.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  const rows = positions.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="staff-positions">
      {canManage ? (
        <Button
          onClick={() => {
            setError(null);
            setForm({ ...EMPTY_FORM });
          }}
        >
          {t("staff.position.add")}
        </Button>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState title={t("staff.position.empty")} />
      ) : (
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t("staff.position.title")}>
          <table className="ui-table" data-testid="positions-table">
            <thead>
              <tr>
                <th scope="col">{t("staff.position.code")}</th>
                <th scope="col">{t("staff.position.name")}</th>
                <th scope="col">{t("staff.position.department")}</th>
                <th scope="col">{t("staff.position.teaching")}</th>
                <th scope="col">{t("staff.position.active")}</th>
                <th scope="col">{t("staff.common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((position) => (
                <tr key={position.id} data-testid={`position-row-${position.id}`}>
                  <td className="ui-num">{position.code}</td>
                  <td>{position.name}</td>
                  <td>{position.department_name ?? t("staff.not_set")}</td>
                  <td>{position.is_teaching ? t("common.yes") : t("common.no")}</td>
                  <td>{position.is_active ? t("common.yes") : t("common.no")}</td>
                  <td>
                    {canManage ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setError(null);
                          setForm(formOf(position));
                        }}
                      >
                        {t("staff.position.edit")}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog
        open={form !== null}
        onClose={() => setForm(null)}
        title={t(form?.id ? "staff.position.edit" : "staff.position.add")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" form="position-form" disabled={save.isPending}>
              {save.isPending ? t("staff.position.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        {form ? (
          <form id="position-form" className="space-y-3" onSubmit={submit}>
            <Field label={t("staff.position.code")}>
              <Input
                required
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value })}
              />
            </Field>
            <Field label={t("staff.position.name")}>
              <Input
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <Field label={t("staff.position.name_am")}>
              <Input
                lang="am"
                dir="auto"
                value={form.name_am}
                onChange={(event) => setForm({ ...form, name_am: event.target.value })}
              />
            </Field>
            <Field label={t("staff.position.department")}>
              <Select
                value={form.department_id}
                onChange={(event) => setForm({ ...form, department_id: event.target.value })}
              >
                <option value="">{t("staff.filter.all_departments")}</option>
                {(departments.data?.items ?? []).map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.position.description")}>
              <Textarea
                rows={3}
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </Field>
            <Field label={t("staff.position.sort_order")}>
              <Input
                type="number"
                min={0}
                value={form.sort_order}
                onChange={(event) => setForm({ ...form, sort_order: event.target.value })}
              />
            </Field>
            <Checkbox
              label={t("staff.position.teaching")}
              checked={form.is_teaching}
              onChange={(event) => setForm({ ...form, is_teaching: event.target.checked })}
            />
            <Checkbox
              label={t("staff.position.active")}
              checked={form.is_active}
              onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
            />
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
          </form>
        ) : null}
      </Dialog>
    </div>
  );
}
