import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
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

import { CalendarDatePicker } from "../../components/CalendarDatePicker";
import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { useYears } from "../academics/queries";
import {
  STAFF,
  useLeaveBalances,
  useLeaveRequests,
  useLeaveTypes,
} from "./queries";
import type {
  LeaveBalance,
  LeaveRequest,
  LeaveStatus,
} from "./types";

function statusVariant(
  status: LeaveStatus,
): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "approved") return "success";
  if (status === "submitted") return "warning";
  if (status === "rejected") return "danger";
  if (status === "draft") return "info";
  return "neutral";
}

interface RequestForm {
  leave_type_id: string;
  year_id: string;
  start_date: string;
  end_date: string;
  is_half_day: boolean;
  reason: string;
}

interface BalanceForm {
  leave_type_id: string;
  year_id: string;
  entitled_days: string;
  carried_days: string;
  adjustment_days: string;
  notes: string;
  row_version: number | null;
}

interface DecisionForm {
  request: LeaveRequest;
  action: "approve" | "reject";
  note: string;
}

export function StaffLeave({
  staffId,
  canRequest,
  canApprove,
  canManageBalances,
}: {
  staffId: string;
  canRequest: boolean;
  canApprove: boolean;
  canManageBalances: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const balances = useLeaveBalances(staffId, true);
  const requests = useLeaveRequests({ staffId });
  const leaveTypes = useLeaveTypes();
  const years = useYears();
  const [requestForm, setRequestForm] = useState<RequestForm | null>(null);
  const [balanceForm, setBalanceForm] = useState<BalanceForm | null>(null);
  const [decision, setDecision] = useState<DecisionForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["staff", "leave-balances", staffId] });
    void queryClient.invalidateQueries({ queryKey: ["staff", "leave-requests", { staffId }] });
    void queryClient.invalidateQueries({ queryKey: ["staff", "leave-calendar"] });
  }

  const createRequest = useMutation({
    mutationFn: (data: RequestForm) =>
      api.post<LeaveRequest>(`${STAFF}/leave-requests`, {
        staff_id: staffId,
        year_id: data.year_id,
        leave_type_id: data.leave_type_id,
        start_date: data.start_date,
        end_date: data.end_date,
        is_half_day: data.is_half_day,
        reason: data.reason.trim() || null,
      }),
    onSuccess: () => {
      refresh();
      setRequestForm(null);
      setMessage(t("staff.leave.request.created"));
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.leave.request.failed"),
      );
    },
  });

  const setBalance = useMutation({
    mutationFn: (data: BalanceForm) =>
      api.put<LeaveBalance>(`${STAFF}/leave-balances`, {
        staff_id: staffId,
        year_id: data.year_id,
        leave_type_id: data.leave_type_id,
        entitled_days: Number(data.entitled_days || 0),
        carried_days: Number(data.carried_days || 0),
        adjustment_days: Number(data.adjustment_days || 0),
        notes: data.notes.trim() || null,
        ...(data.row_version ? { row_version: data.row_version } : {}),
      }),
    onSuccess: () => {
      refresh();
      setBalanceForm(null);
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.leave.balance.failed"),
      );
    },
  });

  const transition = useMutation({
    mutationFn: ({
      request,
      action,
      note,
    }: {
      request: LeaveRequest;
      action: "submit" | "cancel" | "approve" | "reject";
      note?: string;
    }) => {
      if (action === "submit") {
        return api.post<LeaveRequest>(`${STAFF}/leave-requests/${request.id}/submit`);
      }
      if (action === "cancel") {
        return api.post<LeaveRequest>(`${STAFF}/leave-requests/${request.id}/cancel`);
      }
      return api.post<LeaveRequest>(`${STAFF}/leave-requests/${request.id}/${action}`, {
        note: note?.trim() || null,
      });
    },
    onSuccess: () => {
      refresh();
      setDecision(null);
    },
    onError: (caught) => {
      setError(
        caught instanceof ApiRequestError ? caught.message : t("staff.leave.request.decide_failed"),
      );
    },
  });

  function submitRequest(event: FormEvent) {
    event.preventDefault();
    if (!requestForm) return;
    setError(null);
    setMessage(null);
    createRequest.mutate(requestForm);
  }

  function submitBalance(event: FormEvent) {
    event.preventDefault();
    if (!balanceForm) return;
    setError(null);
    setBalance.mutate(balanceForm);
  }

  function submitDecision(event: FormEvent) {
    event.preventDefault();
    if (!decision) return;
    setError(null);
    transition.mutate({
      request: decision.request,
      action: decision.action,
      note: decision.note,
    });
  }

  if (balances.isPending || requests.isPending) {
    return <LoadingState label={t("common.loading")} testId="leave-loading" />;
  }
  if (balances.isError || requests.isError) {
    return (
      <ErrorState
        title={t("staff.load_error")}
        requestId={requestIdOf(balances.error ?? requests.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button
            variant="outline"
            onClick={() => {
              void balances.refetch();
              void requests.refetch();
            }}
          >
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  const balanceRows = balances.data?.items ?? [];
  const requestRows = requests.data?.items ?? [];
  const typeOptions = (leaveTypes.data?.items ?? []).filter((type) => type.is_active);
  const yearOptions = years.data?.items ?? [];

  return (
    <div className="space-y-6" data-testid="staff-leave">
      <div className="flex flex-wrap gap-2">
        {canRequest ? (
          <Button
            onClick={() => {
              setError(null);
              setMessage(null);
              setRequestForm({
                leave_type_id: "",
                year_id: "",
                start_date: "",
                end_date: "",
                is_half_day: false,
                reason: "",
              });
            }}
          >
            {t("staff.leave.request.add")}
          </Button>
        ) : null}
        {canManageBalances ? (
          <Button
            variant="outline"
            onClick={() => {
              setError(null);
              setMessage(null);
              setBalanceForm({
                leave_type_id: "",
                year_id: "",
                entitled_days: "0",
                carried_days: "0",
                adjustment_days: "0",
                notes: "",
                row_version: null,
              });
            }}
          >
            {t("staff.leave.balance.set")}
          </Button>
        ) : null}
      </div>

      {message ? (
        <p role="status" className="text-sm text-primary">
          {message}
        </p>
      ) : null}

      <section className="space-y-3">
        <h3 className="text-sm font-semibold">{t("staff.leave.balance.title")}</h3>
        {balanceRows.length === 0 ? (
          <EmptyState title={t("staff.leave.balance.empty")} />
        ) : (
          <div
            className="overflow-x-auto"
            tabIndex={0}
            role="region"
            aria-label={t("staff.leave.balance.title")}
          >
            <table className="ui-table" data-testid="leave-balances-table">
              <thead>
                <tr>
                  <th scope="col">{t("staff.leave.request.type")}</th>
                  <th scope="col">{t("staff.leave.balance.year")}</th>
                  <th scope="col">{t("staff.leave.balance.entitled")}</th>
                  <th scope="col">{t("staff.leave.balance.carried")}</th>
                  <th scope="col">{t("staff.leave.balance.adjustment")}</th>
                  <th scope="col">{t("staff.leave.balance.used")}</th>
                  <th scope="col">{t("staff.leave.balance.pending")}</th>
                  <th scope="col">{t("staff.leave.balance.remaining")}</th>
                  <th scope="col">{t("staff.common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {balanceRows.map((balance) => (
                  <tr key={balance.id} data-testid={`leave-balance-row-${balance.id}`}>
                    <td>{balance.leave_type_name}</td>
                    <td>{balance.year_code}</td>
                    <td className="ui-num">{balance.entitled_days}</td>
                    <td className="ui-num">{balance.carried_days}</td>
                    <td className="ui-num">{balance.adjustment_days}</td>
                    <td className="ui-num">{balance.used_days}</td>
                    <td className="ui-num">{balance.pending_days}</td>
                    <td className="ui-num">{balance.remaining_days}</td>
                    <td>
                      {canManageBalances ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setError(null);
                            setBalanceForm({
                              leave_type_id: balance.leave_type_id,
                              year_id: balance.year_id,
                              entitled_days: String(balance.entitled_days),
                              carried_days: String(balance.carried_days),
                              adjustment_days: String(balance.adjustment_days),
                              notes: balance.notes ?? "",
                              row_version: balance.row_version,
                            });
                          }}
                        >
                          {t("staff.leave.balance.set")}
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold">{t("staff.leave.request.title")}</h3>
        {requestRows.length === 0 ? (
          <EmptyState title={t("staff.leave.request.empty")} />
        ) : (
          <div
            className="overflow-x-auto"
            tabIndex={0}
            role="region"
            aria-label={t("staff.leave.request.title")}
          >
            <table className="ui-table" data-testid="leave-requests-table">
              <thead>
                <tr>
                  <th scope="col">{t("staff.leave.request.type")}</th>
                  <th scope="col">{t("staff.leave.request.start_date")}</th>
                  <th scope="col">{t("staff.leave.request.end_date")}</th>
                  <th scope="col">{t("staff.leave.request.days")}</th>
                  <th scope="col">{t("staff.leave.request.status")}</th>
                  <th scope="col">{t("staff.common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {requestRows.map((request) => (
                  <tr key={request.id} data-testid={`leave-request-row-${request.id}`}>
                    <td>{request.leave_type_name}</td>
                    <td>{request.start_date}</td>
                    <td>{request.end_date}</td>
                    <td className="ui-num">{request.days}</td>
                    <td>
                      <Badge variant={statusVariant(request.status)}>
                        {t(`staff.leave.status.${request.status}`)}
                      </Badge>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {canRequest && request.status === "draft" ? (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={transition.isPending}
                            onClick={() =>
                              transition.mutate({ request, action: "submit" })
                            }
                          >
                            {t("staff.leave.request.submit")}
                          </Button>
                        ) : null}
                        {canApprove && request.status === "submitted" ? (
                          <>
                            <Button
                              size="sm"
                              disabled={transition.isPending}
                              onClick={() => {
                                setError(null);
                                setDecision({ request, action: "approve", note: "" });
                              }}
                            >
                              {t("staff.leave.request.approve")}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={transition.isPending}
                              onClick={() => {
                                setError(null);
                                setDecision({ request, action: "reject", note: "" });
                              }}
                            >
                              {t("staff.leave.request.reject")}
                            </Button>
                          </>
                        ) : null}
                        {request.status === "draft" ||
                        request.status === "submitted" ||
                        request.status === "approved" ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={transition.isPending}
                            onClick={() => transition.mutate({ request, action: "cancel" })}
                          >
                            {t("staff.leave.request.cancel")}
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <Dialog
        open={requestForm !== null}
        onClose={() => setRequestForm(null)}
        title={t("staff.leave.request.add_title")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRequestForm(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              form="leave-request-form"
              disabled={
                !requestForm?.leave_type_id ||
                !requestForm.year_id ||
                !requestForm.start_date ||
                !requestForm.end_date ||
                createRequest.isPending
              }
            >
              {createRequest.isPending
                ? t("staff.leave.request.saving")
                : t("common.save")}
            </Button>
          </>
        }
      >
        {requestForm ? (
          <form id="leave-request-form" className="space-y-3" onSubmit={submitRequest}>
            <Field label={t("staff.leave.request.type")}>
              <Select
                required
                data-testid="leave-request-type"
                value={requestForm.leave_type_id}
                onChange={(event) =>
                  setRequestForm({ ...requestForm, leave_type_id: event.target.value })
                }
              >
                <option value="">{t("staff.not_set")}</option>
                {typeOptions.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.leave.balance.year")}>
              <Select
                required
                data-testid="leave-request-year"
                value={requestForm.year_id}
                onChange={(event) =>
                  setRequestForm({ ...requestForm, year_id: event.target.value })
                }
              >
                <option value="">{t("staff.not_set")}</option>
                {yearOptions.map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.leave.request.start_date")}>
              <CalendarDatePicker
                value={requestForm.start_date}
                testId="leave-request-start"
                onChange={(value) =>
                  setRequestForm({
                    ...requestForm,
                    start_date: value,
                    end_date: requestForm.is_half_day ? value : requestForm.end_date,
                  })
                }
              />
            </Field>
            <Field label={t("staff.leave.request.end_date")}>
              <CalendarDatePicker
                value={requestForm.end_date}
                testId="leave-request-end"
                onChange={(value) => setRequestForm({ ...requestForm, end_date: value })}
              />
            </Field>
            <Checkbox
              label={t("staff.leave.request.half_day")}
              checked={requestForm.is_half_day}
              onChange={(event) =>
                setRequestForm({
                  ...requestForm,
                  is_half_day: event.target.checked,
                  end_date: event.target.checked
                    ? requestForm.start_date
                    : requestForm.end_date,
                })
              }
            />
            <Field label={t("staff.leave.request.reason")}>
              <Textarea
                rows={3}
                data-testid="leave-request-reason"
                value={requestForm.reason}
                onChange={(event) =>
                  setRequestForm({ ...requestForm, reason: event.target.value })
                }
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

      <Dialog
        open={balanceForm !== null}
        onClose={() => setBalanceForm(null)}
        title={t("staff.leave.balance.set")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setBalanceForm(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              form="leave-balance-form"
              disabled={!balanceForm?.leave_type_id || !balanceForm.year_id || setBalance.isPending}
            >
              {setBalance.isPending
                ? t("staff.leave.balance.saving")
                : t("common.save")}
            </Button>
          </>
        }
      >
        {balanceForm ? (
          <form id="leave-balance-form" className="space-y-3" onSubmit={submitBalance}>
            <Field label={t("staff.leave.request.type")}>
              <Select
                required
                value={balanceForm.leave_type_id}
                onChange={(event) =>
                  setBalanceForm({ ...balanceForm, leave_type_id: event.target.value })
                }
              >
                <option value="">{t("staff.not_set")}</option>
                {(leaveTypes.data?.items ?? []).map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.leave.balance.year")}>
              <Select
                required
                value={balanceForm.year_id}
                onChange={(event) =>
                  setBalanceForm({ ...balanceForm, year_id: event.target.value })
                }
              >
                <option value="">{t("staff.not_set")}</option>
                {yearOptions.map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("staff.leave.balance.entitled")}>
              <Input
                type="number"
                min={0}
                max={365}
                step={0.5}
                value={balanceForm.entitled_days}
                onChange={(event) =>
                  setBalanceForm({ ...balanceForm, entitled_days: event.target.value })
                }
              />
            </Field>
            <Field label={t("staff.leave.balance.carried")}>
              <Input
                type="number"
                min={0}
                max={365}
                step={0.5}
                value={balanceForm.carried_days}
                onChange={(event) =>
                  setBalanceForm({ ...balanceForm, carried_days: event.target.value })
                }
              />
            </Field>
            <Field label={t("staff.leave.balance.adjustment")}>
              <Input
                type="number"
                min={-365}
                max={365}
                step={0.5}
                value={balanceForm.adjustment_days}
                onChange={(event) =>
                  setBalanceForm({ ...balanceForm, adjustment_days: event.target.value })
                }
              />
            </Field>
            <Field label={t("staff.leave.balance.notes")}>
              <Textarea
                rows={3}
                value={balanceForm.notes}
                onChange={(event) =>
                  setBalanceForm({ ...balanceForm, notes: event.target.value })
                }
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

      <Dialog
        open={decision !== null}
        onClose={() => setDecision(null)}
        title={t("staff.leave.request.decision_title")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDecision(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              form="leave-decision-form"
              disabled={transition.isPending}
            >
              {transition.isPending
                ? t(
                    decision?.action === "reject"
                      ? "staff.leave.request.rejecting"
                      : "staff.leave.request.approving",
                  )
                : t("common.save")}
            </Button>
          </>
        }
      >
        {decision ? (
          <form id="leave-decision-form" className="space-y-3" onSubmit={submitDecision}>
            <p className="text-sm text-muted-foreground">
              {decision.request.staff_name} · {decision.request.leave_type_name} ·{" "}
              {decision.request.start_date} – {decision.request.end_date}
            </p>
            <Field label={t("staff.leave.request.decision_note")}>
              <Textarea
                rows={3}
                data-testid="leave-decision-note"
                value={decision.note}
                onChange={(event) => setDecision({ ...decision, note: event.target.value })}
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
