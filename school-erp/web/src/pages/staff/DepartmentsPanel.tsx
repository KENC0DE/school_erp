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
import { STAFF, useDepartments } from "./queries";
import type { Department } from "./types";

interface DepartmentForm {
  id: string | null;
  code: string;
  name: string;
  name_am: string;
  parent_id: string;
  description: string;
  is_active: boolean;
  sort_order: string;
  row_version: number;
}

const EMPTY_FORM: DepartmentForm = {
  id: null,
  code: "",
  name: "",
  name_am: "",
  parent_id: "",
  description: "",
  is_active: true,
  sort_order: "0",
  row_version: 0,
};

function formOf(department: Department): DepartmentForm {
  return {
    id: department.id,
    code: department.code,
    name: department.name,
    name_am: department.name_am ?? "",
    parent_id: department.parent_id ?? "",
    description: department.description ?? "",
    is_active: department.is_active,
    sort_order: String(department.sort_order),
    row_version: department.row_version,
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function DepartmentsPanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const departments = useDepartments(true);
  const [form, setForm] = useState<DepartmentForm | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (data: DepartmentForm) => {
      const body = {
        code: data.code.trim(),
        name: data.name.trim(),
        name_am: clean(data.name_am),
        parent_id: data.parent_id || null,
        description: clean(data.description),
        is_active: data.is_active,
        sort_order: Number(data.sort_order || 0),
      };
      return data.id
        ? api.patch<Department>(`${STAFF}/departments/${data.id}`, {
            ...body,
            row_version: data.row_version,
          })
        : api.post<Department>(`${STAFF}/departments`, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "departments"] });
      setForm(null);
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.department.failed"),
      );
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setError(null);
    save.mutate(form);
  }

  if (departments.isPending) {
    return <LoadingState label={t("common.loading")} testId="departments-loading" />;
  }
  if (departments.isError) {
    return (
      <ErrorState
        title={t("staff.load_error")}
        requestId={requestIdOf(departments.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button variant="outline" onClick={() => void departments.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  const rows = departments.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="staff-departments">
      {canManage ? (
        <Button
          onClick={() => {
            setError(null);
            setForm({ ...EMPTY_FORM });
          }}
        >
          {t("staff.department.add")}
        </Button>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState title={t("staff.department.empty")} />
      ) : (
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t("staff.department.title")}>
          <table className="ui-table" data-testid="departments-table">
            <thead>
              <tr>
                <th scope="col">{t("staff.department.code")}</th>
                <th scope="col">{t("staff.department.name")}</th>
                <th scope="col">{t("staff.department.sort_order")}</th>
                <th scope="col">{t("staff.department.active")}</th>
                <th scope="col">{t("staff.common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((department) => (
                <tr key={department.id} data-testid={`department-row-${department.id}`}>
                  <td className="ui-num">{department.code}</td>
                  <td>
                    {department.name}
                    {department.name_am ? (
                      <span className="block text-xs text-muted-foreground" lang="am" dir="auto">
                        {department.name_am}
                      </span>
                    ) : null}
                  </td>
                  <td>{department.sort_order}</td>
                  <td>
                    {department.is_active ? t("common.yes") : t("common.no")}
                  </td>
                  <td>
                    {canManage ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setError(null);
                          setForm(formOf(department));
                        }}
                      >
                        {t("staff.department.edit")}
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
        title={t(form?.id ? "staff.department.edit" : "staff.department.add")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" form="department-form" disabled={save.isPending}>
              {save.isPending ? t("staff.department.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        {form ? (
          <form id="department-form" className="space-y-3" onSubmit={submit}>
            <Field label={t("staff.department.code")}>
              <Input
                required
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value })}
              />
            </Field>
            <Field label={t("staff.department.name")}>
              <Input
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <Field label={t("staff.department.name_am")}>
              <Input
                lang="am"
                dir="auto"
                value={form.name_am}
                onChange={(event) => setForm({ ...form, name_am: event.target.value })}
              />
            </Field>
            <Field label={t("staff.department.parent")}>
              <Select
                value={form.parent_id}
                onChange={(event) => setForm({ ...form, parent_id: event.target.value })}
              >
                <option value="">{t("staff.filter.all_departments")}</option>
                {rows
                  .filter((department) => department.id !== form.id)
                  .map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name}
                    </option>
                  ))}
              </Select>
            </Field>
            <Field label={t("staff.department.description")}>
              <Textarea
                rows={3}
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </Field>
            <Field label={t("staff.department.sort_order")}>
              <Input
                type="number"
                min={0}
                value={form.sort_order}
                onChange={(event) => setForm({ ...form, sort_order: event.target.value })}
              />
            </Field>
            <Checkbox
              label={t("staff.department.active")}
              checked={form.is_active}
              onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
            />
            <p className="text-xs text-muted-foreground">
              {t("staff.department.active_help")}
            </p>
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
