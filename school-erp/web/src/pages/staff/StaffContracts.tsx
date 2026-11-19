import { ApiRequestError } from "@erp/api-client";
import { formatSantim, parseMoney } from "@erp/money";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Button,
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

import { CalendarDatePicker } from "../../components/CalendarDatePicker";
import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { STAFF, useStaffContracts } from "./queries";
import {
  CONTRACT_STATUSES,
  CONTRACT_TYPES,
  type Contract,
  type ContractStatus,
  type ContractType,
} from "./types";

interface ContractForm {
  id: string | null;
  type: ContractType;
  status: ContractStatus;
  start_date: string;
  end_date: string;
  salary: string;
  notes: string;
  row_version: number;
}

const EMPTY_FORM: ContractForm = {
  id: null,
  type: "permanent",
  status: "active",
  start_date: "",
  end_date: "",
  salary: "",
  notes: "",
  row_version: 0,
};

function formOf(contract: Contract): ContractForm {
  return {
    id: contract.id,
    type: contract.type,
    status: contract.status,
    start_date: contract.start_date,
    end_date: contract.end_date ?? "",
    salary: contract.salary_santim === null
      ? ""
      : formatSantim(contract.salary_santim, { withCurrency: false }).replace(/,/g, ""),
    notes: contract.notes ?? "",
    row_version: contract.row_version,
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function StaffContracts({
  staffId,
  canManage,
}: {
  staffId: string;
  canManage: boolean;
}) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const contracts = useStaffContracts(staffId, true);
  const [form, setForm] = useState<ContractForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (data: ContractForm) => {
      const body = {
        type: data.type,
        status: data.status,
        start_date: data.start_date,
        end_date: clean(data.end_date),
        salary_santim: data.salary.trim() ? parseMoney(data.salary) : null,
        notes: clean(data.notes),
      };
      return data.id
        ? api.patch<Contract>(`${STAFF}/${staffId}/contracts/${data.id}`, {
            ...body,
            row_version: data.row_version,
          })
        : api.post<Contract>(`${STAFF}/${staffId}/contracts`, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "contracts", staffId] });
      void queryClient.invalidateQueries({ queryKey: ["staff", "detail", staffId] });
      setForm(null);
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.contract.failed"),
      );
    },
  });

  const remove = useMutation({
    mutationFn: (contractId: string) =>
      api.del(`${STAFF}/${staffId}/contracts/${contractId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "contracts", staffId] });
      void queryClient.invalidateQueries({ queryKey: ["staff", "detail", staffId] });
      setMessage(t("staff.contract.deleted"));
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.contract.failed"),
      );
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setError(null);
    save.mutate(form);
  }

  if (contracts.isPending) {
    return <LoadingState label={t("common.loading")} testId="contracts-loading" />;
  }
  if (contracts.isError) {
    return (
      <ErrorState
        title={t("staff.load_error")}
        requestId={requestIdOf(contracts.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button variant="outline" onClick={() => void contracts.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  const rows = contracts.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="staff-contracts">
      {canManage ? (
        <Button
          onClick={() => {
            setError(null);
            setMessage(null);
            setForm({ ...EMPTY_FORM });
          }}
        >
          {t("staff.contract.add")}
        </Button>
      ) : null}
      {message ? (
        <p role="status" className="text-sm text-primary">
          {message}
        </p>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState title={t("staff.contract.empty")} />
      ) : (
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={t("staff.contract.title")}>
          <table className="ui-table" data-testid="contracts-table">
            <thead>
              <tr>
                <th scope="col">{t("staff.contract.type")}</th>
                <th scope="col">{t("staff.contract.status")}</th>
                <th scope="col">{t("staff.contract.start_date")}</th>
                <th scope="col">{t("staff.contract.end_date")}</th>
                <th scope="col">{t("staff.contract.salary")}</th>
                <th scope="col">{t("staff.common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((contract) => (
                <tr key={contract.id} data-testid={`contract-row-${contract.id}`}>
                  <td>{t(`staff.contract.type.${contract.type}`)}</td>
                  <td>{t(`staff.contract.status.${contract.status}`)}</td>
                  <td>{contract.start_date}</td>
                  <td>{contract.end_date ?? t("staff.not_set")}</td>
                  <td className="ui-num">
                    {contract.salary_santim === null
                      ? t("staff.not_set")
                      : formatSantim(contract.salary_santim, { locale })}
                  </td>
                  <td>
                    {canManage ? (
                      <div className="flex flex-wrap gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setError(null);
                            setMessage(null);
                            setForm(formOf(contract));
                          }}
                        >
                          {t("staff.contract.edit")}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={remove.isPending}
                          onClick={() => remove.mutate(contract.id)}
                        >
                          {t("staff.contract.delete")}
                        </Button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <Dialog
        open={form !== null}
        onClose={() => setForm(null)}
        title={t(form?.id ? "staff.contract.edit" : "staff.contract.add")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" form="contract-form" disabled={save.isPending}>
              {save.isPending ? t("staff.contract.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        {form ? (
          <form id="contract-form" className="space-y-3" onSubmit={submit}>
            <Field label={t("staff.contract.type")}>
              <Select
                value={form.type}
                onChange={(event) =>
                  setForm({ ...form, type: event.target.value as ContractType })
                }
              >
                {CONTRACT_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {t(`staff.contract.type.${value}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.contract.status")}>
              <Select
                value={form.status}
                onChange={(event) =>
                  setForm({ ...form, status: event.target.value as ContractStatus })
                }
              >
                {CONTRACT_STATUSES.map((value) => (
                  <option key={value} value={value}>
                    {t(`staff.contract.status.${value}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.contract.start_date")}>
              <CalendarDatePicker
                value={form.start_date}
                onChange={(value) => setForm({ ...form, start_date: value })}
              />
            </Field>
            <Field label={t("staff.contract.end_date")}>
              <CalendarDatePicker
                value={form.end_date}
                onChange={(value) => setForm({ ...form, end_date: value })}
              />
            </Field>
            <Field label={t("staff.contract.salary")}>
              <Input
                inputMode="decimal"
                value={form.salary}
                onChange={(event) => setForm({ ...form, salary: event.target.value })}
              />
            </Field>
            <p className="text-xs text-muted-foreground">{t("staff.contract.salary_hint")}</p>
            <Field label={t("staff.contract.notes")}>
              <Textarea
                rows={3}
                value={form.notes}
                onChange={(event) => setForm({ ...form, notes: event.target.value })}
              />
            </Field>
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
