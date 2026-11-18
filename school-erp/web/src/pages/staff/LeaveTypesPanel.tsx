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
  Textarea,
} from "@erp/ui-web";
import { useState, type FormEvent } from "react";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { STAFF, useLeaveTypes } from "./queries";
import type { LeaveType } from "./types";

interface LeaveTypeForm {
  id: string | null;
  code: string;
  name: string;
  name_am: string;
  is_paid: boolean;
  annual_entitlement_days: string;
  counts_against_balance: boolean;
  requires_approval: boolean;
  is_active: boolean;
  sort_order: string;
  notes: string;
  row_version: number;
}

const EMPTY_FORM: LeaveTypeForm = {
  id: null,
  code: "",
  name: "",
  name_am: "",
  is_paid: true,
  annual_entitlement_days: "0",
  counts_against_balance: true,
  requires_approval: true,
  is_active: true,
  sort_order: "0",
  notes: "",
  row_version: 0,
};

function formOf(leaveType: LeaveType): LeaveTypeForm {
  return {
    id: leaveType.id,
    code: leaveType.code,
    name: leaveType.name,
    name_am: leaveType.name_am ?? "",
    is_paid: leaveType.is_paid,
    annual_entitlement_days: String(leaveType.annual_entitlement_days),
    counts_against_balance: leaveType.counts_against_balance,
    requires_approval: leaveType.requires_approval,
    is_active: leaveType.is_active,
    sort_order: String(leaveType.sort_order),
    notes: leaveType.notes ?? "",
    row_version: leaveType.row_version,
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function LeaveTypesPanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const leaveTypes = useLeaveTypes(true);
  const [form, setForm] = useState<LeaveTypeForm | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (data: LeaveTypeForm) => {
      const body = {
        code: data.code.trim(),
        name: data.name.trim(),
        name_am: clean(data.name_am),
        is_paid: data.is_paid,
        annual_entitlement_days: Number(data.annual_entitlement_days || 0),
        counts_against_balance: data.counts_against_balance,
        requires_approval: data.requires_approval,
        is_active: data.is_active,
        sort_order: Number(data.sort_order || 0),
        notes: clean(data.notes),
      };
      return data.id
        ? api.patch<LeaveType>(`${STAFF}/leave-types/${data.id}`, {
            ...body,
            row_version: data.row_version,
          })
        : api.post<LeaveType>(`${STAFF}/leave-types`, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "leave-types"] });
      setForm(null);
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.leave.type.failed"),
      );
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setError(null);
    save.mutate(form);
  }

  if (leaveTypes.isPending) {
    return <LoadingState label={t("common.loading")} testId="leave-types-loading" />;
  }
  if (leaveTypes.isError) {
    return (
      <ErrorState
        title={t("staff.load_error")}
        requestId={requestIdOf(leaveTypes.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button variant="outline" onClick={() => void leaveTypes.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  const rows = leaveTypes.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="staff-leave-types">
      {canManage ? (
        <Button
          onClick={() => {
            setError(null);
            setForm({ ...EMPTY_FORM });
          }}
        >
          {t("staff.leave.type.add")}
        </Button>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState title={t("staff.leave.type.empty")} />
      ) : (
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t("staff.leave.type.title")}>
          <table className="ui-table" data-testid="leave-types-table">
            <thead>
              <tr>
                <th scope="col">{t("staff.leave.type.code")}</th>
                <th scope="col">{t("staff.leave.type.name")}</th>
                <th scope="col">{t("staff.leave.type.entitlement")}</th>
                <th scope="col">{t("staff.leave.type.paid")}</th>
                <th scope="col">{t("staff.leave.type.requires_approval")}</th>
                <th scope="col">{t("staff.leave.type.active")}</th>
                <th scope="col">{t("staff.common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((leaveType) => (
                <tr key={leaveType.id} data-testid={`leave-type-row-${leaveType.id}`}>
                  <td className="ui-num">{leaveType.code}</td>
                  <td>{leaveType.name}</td>
                  <td className="ui-num">{leaveType.annual_entitlement_days}</td>
                  <td>{leaveType.is_paid ? t("common.yes") : t("common.no")}</td>
                  <td>{leaveType.requires_approval ? t("common.yes") : t("common.no")}</td>
                  <td>{leaveType.is_active ? t("common.yes") : t("common.no")}</td>
                  <td>
                    {canManage ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setError(null);
                          setForm(formOf(leaveType));
                        }}
                      >
                        {t("staff.leave.type.edit")}
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
        title={t(form?.id ? "staff.leave.type.edit" : "staff.leave.type.add")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" form="leave-type-form" disabled={save.isPending}>
              {save.isPending ? t("staff.leave.type.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        {form ? (
          <form id="leave-type-form" className="space-y-3" onSubmit={submit}>
            <Field label={t("staff.leave.type.code")}>
              <Input
                required
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value })}
              />
            </Field>
            <Field label={t("staff.leave.type.name")}>
              <Input
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <Field label={t("staff.leave.type.name_am")}>
              <Input
                lang="am"
                dir="auto"
                value={form.name_am}
                onChange={(event) => setForm({ ...form, name_am: event.target.value })}
              />
            </Field>
            <Field label={t("staff.leave.type.entitlement")}>
              <Input
                type="number"
                min={0}
                max={365}
                step={0.5}
                value={form.annual_entitlement_days}
                onChange={(event) =>
                  setForm({ ...form, annual_entitlement_days: event.target.value })
                }
              />
            </Field>
            <Field label={t("staff.leave.type.sort_order")}>
              <Input
                type="number"
                min={0}
                value={form.sort_order}
                onChange={(event) => setForm({ ...form, sort_order: event.target.value })}
              />
            </Field>
            <Field label={t("staff.leave.type.notes")}>
              <Textarea
                rows={3}
                value={form.notes}
                onChange={(event) => setForm({ ...form, notes: event.target.value })}
              />
            </Field>
            <Checkbox
              label={t("staff.leave.type.paid")}
              checked={form.is_paid}
              onChange={(event) => setForm({ ...form, is_paid: event.target.checked })}
            />
            <Checkbox
              label={t("staff.leave.type.counts_against_balance")}
              checked={form.counts_against_balance}
              onChange={(event) =>
                setForm({ ...form, counts_against_balance: event.target.checked })
              }
            />
            <Checkbox
              label={t("staff.leave.type.requires_approval")}
              checked={form.requires_approval}
              onChange={(event) => setForm({ ...form, requires_approval: event.target.checked })}
            />
            <Checkbox
              label={t("staff.leave.type.active")}
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
