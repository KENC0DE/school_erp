import { ApiRequestError } from "@erp/api-client";
import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  Input,
  LoadingState,
  Page,
  PageHeader,
  Tabs,
} from "@erp/ui-web";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { DepartmentsPanel } from "./DepartmentsPanel";
import { LeaveTypesPanel } from "./LeaveTypesPanel";
import { PositionsPanel } from "./PositionsPanel";
import { StaffFormDialog } from "./StaffFormDialog";
import { StaffLeaveCalendar } from "./StaffLeaveCalendar";
import {
  hasPermission,
  useDepartments,
  usePositions,
  useStaff,
} from "./queries";
import {
  EMPTY_FILTERS,
  STAFF_STATUSES,
  type StaffFilters,
  type StaffStatus,
  type StaffSummary,
} from "./types";

function statusVariant(
  status: StaffStatus,
): "neutral" | "success" | "warning" | "danger" {
  if (status === "active") return "success";
  if (status === "on_leave") return "warning";
  if (status === "terminated") return "danger";
  return "neutral";
}

export function StaffPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const canView = hasPermission(user?.permissions, "staff.view");
  const canManage = hasPermission(user?.permissions, "staff.manage");
  const canViewLeave = hasPermission(user?.permissions, "staff.leave.view");
  const canManageLeave = hasPermission(user?.permissions, "staff.leave.manage");

  const [filters, setFilters] = useState<StaffFilters>({ ...EMPTY_FILTERS });
  const [draftQuery, setDraftQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<StaffSummary | null>(null);

  const departments = useDepartments();
  const positions = usePositions(filters.department_id);
  const staff = useStaff(filters, null);

  if (!canView) {
    return (
      <Page>
        <Card>
          <CardContent className="p-6">
            <EmptyState title={t("staff.perm.view")} />
          </CardContent>
        </Card>
      </Page>
    );
  }

  const rows = staff.data?.items ?? [];

  function onSearch(event: FormEvent) {
    event.preventDefault();
    setFilters((current) => ({ ...current, q: draftQuery.trim() }));
    setCreated(null);
  }

  const directory = (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-4 p-4">
          <form className="flex flex-wrap items-end gap-3" onSubmit={onSearch}>
            <label className="min-w-60 flex-1 space-y-1 text-sm">
              <span className="font-medium">{t("staff.search.label")}</span>
              <Input
                data-testid="staff-search"
                value={draftQuery}
                placeholder={t("staff.search.placeholder")}
                onChange={(event) => setDraftQuery(event.target.value)}
              />
            </label>
            <Button type="submit" variant="outline">
              {t("staff.search.action")}
            </Button>
            {canManage ? (
              <Button
                data-testid="staff-create-open"
                onClick={() => {
                  setCreated(null);
                  setCreating(true);
                }}
              >
                {t("staff.create.open")}
              </Button>
            ) : null}
          </form>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("staff.status")}</span>
              <select
                className="ui-select"
                data-testid="staff-status-filter"
                value={filters.status}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, status: event.target.value }))
                }
              >
                <option value="">{t("staff.filter.all_statuses")}</option>
                {STAFF_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {t(`staff.status.${status}`)}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("staff.department")}</span>
              <select
                className="ui-select"
                data-testid="staff-department-filter"
                value={filters.department_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    department_id: event.target.value,
                    position_id: "",
                  }))
                }
              >
                <option value="">{t("staff.filter.all_departments")}</option>
                {(departments.data?.items ?? []).map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("staff.position")}</span>
              <select
                className="ui-select"
                data-testid="staff-position-filter"
                value={filters.position_id}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, position_id: event.target.value }))
                }
              >
                <option value="">{t("staff.filter.all_positions")}</option>
                {(positions.data?.items ?? []).map((position) => (
                  <option key={position.id} value={position.id}>
                    {position.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </CardContent>
      </Card>

      {created ? (
        <p role="status" className="text-sm text-primary" data-testid="staff-created">
          {t("staff.create.created", { name: created.person.full_name })}{" "}
          <Link className="ui-link" to={`/staff/${created.id}`}>
            {t("staff.open_profile")}
          </Link>
        </p>
      ) : null}

      {staff.isPending ? (
        <LoadingState label={t("staff.loading")} testId="staff-loading" />
      ) : staff.isError ? (
        <Card>
          <CardContent className="p-6">
            <ErrorState
              title={t("staff.load_error")}
              requestId={requestIdOf(staff.error)}
              requestIdLabel={t("common.request_id")}
              retry={
                <Button variant="outline" onClick={() => void staff.refetch()}>
                  {t("common.retry")}
                </Button>
              }
              testId="staff-error"
            />
          </CardContent>
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="p-6">
            <EmptyState
              title={t("staff.empty")}
              description={t("staff.empty_hint")}
              testId="staff-empty"
              action={
                canManage ? (
                  <Button onClick={() => setCreating(true)}>
                    {t("staff.create.open")}
                  </Button>
                ) : undefined
              }
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent
            className="overflow-x-auto p-0"
            tabIndex={0}
            role="region"
            aria-label={t("staff.title")}
          >
            <table className="ui-table" data-testid="staff-table">
              <caption className="ui-visually-hidden">{t("staff.title")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("staff.staff_number")}</th>
                  <th scope="col">{t("staff.person")}</th>
                  <th scope="col">{t("staff.department")}</th>
                  <th scope="col">{t("staff.position")}</th>
                  <th scope="col">{t("staff.status")}</th>
                  <th scope="col">{t("staff.hire_date")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((member) => (
                  <tr key={member.id} data-testid={`staff-row-${member.id}`}>
                    <td className="ui-num">
                      <Link className="ui-link" to={`/staff/${member.id}`}>
                        {member.staff_number}
                      </Link>
                    </td>
                    <td>
                      <Link className="ui-link" to={`/staff/${member.id}`}>
                        {member.person.full_name}
                      </Link>
                      {member.person.given_name_am ? (
                        <span className="block text-xs text-muted-foreground" lang="am" dir="auto">
                          {[
                            member.person.given_name_am,
                            member.person.father_name_am,
                            member.person.grandfather_name_am,
                          ]
                            .filter(Boolean)
                            .join(" ")}
                        </span>
                      ) : null}
                    </td>
                    <td>{member.department?.name ?? t("staff.not_set")}</td>
                    <td>{member.position?.name ?? t("staff.not_set")}</td>
                    <td>
                      <Badge variant={statusVariant(member.status)}>
                        {t(`staff.status.${member.status}`)}
                      </Badge>
                    </td>
                    <td>{member.hire_date ?? t("staff.not_set")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
          <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
            {t("staff.count", { count: staff.data?.total ?? rows.length })}
          </p>
        </Card>
      )}

      {staff.isError && staff.error instanceof ApiRequestError ? (
        <p className="text-sm text-destructive">{staff.error.message}</p>
      ) : null}
    </div>
  );

  const panels = [
    { key: "directory", label: t("staff.tab.directory"), content: directory },
    {
      key: "departments",
      label: t("staff.tab.departments"),
      content: <DepartmentsPanel canManage={canManage} />,
    },
    {
      key: "positions",
      label: t("staff.tab.positions"),
      content: <PositionsPanel canManage={canManage} />,
    },
  ];
  if (canViewLeave) {
    panels.push({
      key: "leave-types",
      label: t("staff.tab.leave_types"),
      content: <LeaveTypesPanel canManage={canManageLeave} />,
    });
    panels.push({
      key: "calendar",
      label: t("staff.tab.calendar"),
      content: <StaffLeaveCalendar enabled={canViewLeave} />,
    });
  }

  return (
    <Page>
      <PageHeader title={t("staff.title")} description={t("staff.intro")} />
      <Card>
        <CardContent className="p-4">
          <Tabs items={panels} />
        </CardContent>
      </Card>

      {creating ? (
        <StaffFormDialog
          open={creating}
          onClose={() => setCreating(false)}
          onSaved={(saved) => {
            setCreated(saved);
            void staff.refetch();
          }}
        />
      ) : null}
    </Page>
  );
}
