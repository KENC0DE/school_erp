import {
  Badge,
  Button,
  Card,
  CardContent,
  ErrorState,
  LoadingState,
  Page,
  PageHeader,
  Tabs,
} from "@erp/ui-web";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { StaffContracts } from "./StaffContracts";
import { StaffDocuments } from "./StaffDocuments";
import { StaffFormDialog } from "./StaffFormDialog";
import { StaffLeave } from "./StaffLeave";
import { StaffQualifications } from "./StaffQualifications";
import { StaffTeaching } from "./StaffTeaching";
import { hasPermission, useStaffDetail } from "./queries";
import type { StaffStatus } from "./types";

function statusVariant(
  status: StaffStatus,
): "neutral" | "success" | "warning" | "danger" {
  if (status === "active") return "success";
  if (status === "on_leave") return "warning";
  if (status === "terminated") return "danger";
  return "neutral";
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value}</dd>
    </div>
  );
}

export function StaffProfilePage() {
  const { staffId } = useParams<{ staffId: string }>();
  const { t } = useI18n();
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);

  const staff = useStaffDetail(staffId ?? null);
  const canManage = hasPermission(user?.permissions, "staff.manage");
  const canViewContracts = hasPermission(user?.permissions, "staff.contracts.view");
  const canManageContracts = hasPermission(user?.permissions, "staff.contracts.manage");
  const canViewLeave = hasPermission(user?.permissions, "staff.leave.view");
  const canRequestLeave = hasPermission(user?.permissions, "staff.leave.request");
  const canApproveLeave = hasPermission(user?.permissions, "staff.leave.approve");
  const canManageLeave = hasPermission(user?.permissions, "staff.leave.manage");

  if (staff.isPending) {
    return (
      <Page>
        <LoadingState label={t("staff.loading")} testId="staff-profile-loading" />
      </Page>
    );
  }

  if (staff.isError || !staff.data) {
    return (
      <Page>
        <ErrorState
          title={t("staff.profile_error")}
          requestId={requestIdOf(staff.error)}
          requestIdLabel={t("common.request_id")}
          retry={
            <Button variant="outline" onClick={() => void staff.refetch()}>
              {t("common.retry")}
            </Button>
          }
          testId="staff-profile-error"
        />
        <p className="mt-4">
          <Link className="ui-link" to="/staff">
            {t("staff.back_to_list")}
          </Link>
        </p>
      </Page>
    );
  }

  const detail = staff.data;
  const amharicName = [
    detail.person.given_name_am,
    detail.person.father_name_am,
    detail.person.grandfather_name_am,
  ]
    .filter(Boolean)
    .join(" ");

  const overview = (
    <dl className="grid gap-3 sm:grid-cols-2" data-testid="staff-overview">
      <Detail label={t("staff.staff_number")} value={detail.staff_number} />
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">
          {t("staff.status")}
        </dt>
        <dd className="text-sm">
          <Badge variant={statusVariant(detail.status)}>
            {t(`staff.status.${detail.status}`)}
          </Badge>
        </dd>
      </div>
      <Detail label={t("staff.department")} value={detail.department?.name ?? t("staff.not_set")} />
      <Detail label={t("staff.position")} value={detail.position?.name ?? t("staff.not_set")} />
      <Detail label={t("staff.hire_date")} value={detail.hire_date ?? t("staff.not_set")} />
      <Detail label={t("staff.end_date")} value={detail.end_date ?? t("staff.not_set")} />
      <Detail label={t("staff.person.sex")} value={
        detail.person.sex
          ? t(`staff.person.sex.${detail.person.sex}`)
          : t("staff.person.sex.unspecified")
      } />
      <Detail
        label={t("staff.person.date_of_birth")}
        value={detail.person.date_of_birth ?? t("staff.not_set")}
      />
      <Detail label={t("staff.person.phone")} value={detail.person.phone ?? t("staff.not_set")} />
      <Detail label={t("staff.person.email")} value={detail.person.email ?? t("staff.not_set")} />
      <div className="sm:col-span-2">
        <Detail
          label={t("staff.person.address")}
          value={detail.person.address ?? t("staff.not_set")}
        />
      </div>
      <div className="sm:col-span-2">
        <Detail label={t("staff.user_account")} value={
          detail.user_id ? detail.user_id : t("staff.account.unlinked")
        } />
      </div>
      <div className="sm:col-span-2">
        <Detail label={t("staff.notes")} value={detail.notes || t("staff.not_set")} />
      </div>
    </dl>
  );

  const panels = [
    { key: "overview", label: t("staff.tab.overview"), content: overview },
  ];
  if (canViewContracts) {
    panels.push({
      key: "contracts",
      label: t("staff.contract.title"),
      content: (
        <StaffContracts staffId={detail.id} canManage={canManageContracts} />
      ),
    });
  }
  panels.push(
    {
      key: "qualifications",
      label: t("staff.qualification.title"),
      content: <StaffQualifications staffId={detail.id} canManage={canManage} />,
    },
    {
      key: "teaching",
      label: t("staff.teaching.title"),
      content: <StaffTeaching staffId={detail.id} canManage={canManage} />,
    },
  );
  if (canViewLeave) {
    panels.push({
      key: "leave",
      label: t("staff.leave.request.title"),
      content: (
        <StaffLeave
          staffId={detail.id}
          canRequest={canRequestLeave}
          canApprove={canApproveLeave}
          canManageBalances={canManageLeave}
        />
      ),
    });
  }
  panels.push({
    key: "documents",
    label: t("staff.documents"),
    content: <StaffDocuments staffId={detail.id} canManage={canManage} />,
  });

  return (
    <Page>
      <PageHeader
        breadcrumbs={
          <Link className="ui-link text-sm" to="/staff">
            {t("staff.back_to_list")}
          </Link>
        }
        title={detail.person.full_name}
        description={
          amharicName ? (
            <span lang="am" dir="auto">
              {amharicName}
            </span>
          ) : undefined
        }
        actions={
          canManage ? (
            <Button variant="outline" data-testid="staff-edit-open" onClick={() => setEditing(true)}>
              {t("staff.edit.open")}
            </Button>
          ) : undefined
        }
      />

      <Card>
        <CardContent className="p-4">
          <Tabs items={panels} />
        </CardContent>
      </Card>

      {canManage && editing ? (
        <StaffFormDialog
          open={editing}
          staff={detail}
          onClose={() => {
            setEditing(false);
            void staff.refetch();
          }}
        />
      ) : null}
    </Page>
  );
}
