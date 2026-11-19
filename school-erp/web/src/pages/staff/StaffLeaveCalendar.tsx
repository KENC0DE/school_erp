import { useState } from "react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Select,
} from "@erp/ui-web";

import { CalendarDatePicker } from "../../components/CalendarDatePicker";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { useLeaveCalendar } from "./queries";
import { LEAVE_STATUSES, type LeaveStatus } from "./types";

function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function monthBounds(): { from: string; to: string } {
  const now = new Date();
  const first = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const last = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0));
  return { from: iso(first), to: iso(last) };
}

function statusVariant(
  status: LeaveStatus,
): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "approved") return "success";
  if (status === "submitted") return "warning";
  if (status === "rejected") return "danger";
  if (status === "draft") return "info";
  return "neutral";
}

const INITIAL = monthBounds();

export function StaffLeaveCalendar({ enabled }: { enabled: boolean }) {
  const { t } = useI18n();
  const [fromDate, setFromDate] = useState(INITIAL.from);
  const [toDate, setToDate] = useState(INITIAL.to);
  const [applied, setApplied] = useState({ from: INITIAL.from, to: INITIAL.to });
  const [status, setStatus] = useState("");
  const calendar = useLeaveCalendar(applied.from, applied.to, enabled);

  if (!enabled) {
    return <EmptyState title={t("staff.perm.leave_view")} />;
  }

  const rows = (calendar.data?.items ?? []).filter(
    (request) => !status || request.status === status,
  );

  return (
    <div className="space-y-4" data-testid="staff-leave-calendar">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t("staff.leave.calendar.from")}>
          <CalendarDatePicker value={fromDate} onChange={setFromDate} />
        </Field>
        <Field label={t("staff.leave.calendar.to")}>
          <CalendarDatePicker value={toDate} onChange={setToDate} />
        </Field>
        <Field label={t("staff.leave.calendar.status")}>
          <Select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">{t("staff.leave.request.all_statuses")}</option>
            {LEAVE_STATUSES.map((value) => (
              <option key={value} value={value}>
                {t(`staff.leave.status.${value}`)}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Button
        variant="outline"
        onClick={() => setApplied({ from: fromDate, to: toDate })}
      >
        {t("staff.search.action")}
      </Button>

      {calendar.isPending ? (
        <LoadingState label={t("common.loading")} testId="leave-calendar-loading" />
      ) : calendar.isError ? (
        <ErrorState
          title={t("staff.leave.calendar.load_error")}
          requestId={requestIdOf(calendar.error)}
          requestIdLabel={t("common.request_id")}
          retry={
            <Button variant="outline" onClick={() => void calendar.refetch()}>
              {t("common.retry")}
            </Button>
          }
        />
      ) : rows.length === 0 ? (
        <EmptyState title={t("staff.leave.calendar.empty")} />
      ) : (
        <div
          className="overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label={t("staff.leave.calendar.title")}
        >
          <table className="ui-table" data-testid="leave-calendar-table">
            <thead>
              <tr>
                <th scope="col">{t("staff.leave.request.staff")}</th>
                <th scope="col">{t("staff.leave.request.type")}</th>
                <th scope="col">{t("staff.leave.request.start_date")}</th>
                <th scope="col">{t("staff.leave.request.end_date")}</th>
                <th scope="col">{t("staff.leave.request.days")}</th>
                <th scope="col">{t("staff.leave.request.status")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((request) => (
                <tr key={request.id} data-testid={`leave-calendar-row-${request.id}`}>
                  <td>{request.staff_name}</td>
                  <td>{request.leave_type_name}</td>
                  <td>{request.start_date}</td>
                  <td>{request.end_date}</td>
                  <td className="ui-num">{request.days}</td>
                  <td>
                    <Badge variant={statusVariant(request.status)}>
                      {t(`staff.leave.status.${request.status}`)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
