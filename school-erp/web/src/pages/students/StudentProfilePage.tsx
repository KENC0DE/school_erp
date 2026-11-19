import { useQueryClient } from "@tanstack/react-query";
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  Page,
  PageHeader,
  Tabs,
} from "@erp/ui-web";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "../../components/ui/Badge";
import { Card, CardContent } from "../../components/ui/Card";
import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { hasPermission, useStudent } from "./queries";
import { StudentDocuments } from "./StudentDocuments";
import { StudentEditDialog } from "./StudentEditDialog";
import { StudentGuardians } from "./StudentGuardians";
import { StudentMedical } from "./StudentMedical";
import { StudentPhotoCard } from "./StudentPhotoCard";
import {
  StudentStatusDialog,
  allowedStatusActions,
} from "./StudentStatusDialog";
import type { StudentStatus } from "./types";

function statusVariant(
  status: StudentStatus,
): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "active") return "success";
  if (status === "applicant") return "info";
  if (status === "repeating" || status === "promoted") return "warning";
  if (status === "withdrawn" || status === "transferred_out") return "danger";
  return "neutral";
}

export function StudentProfilePage() {
  const { studentId } = useParams<{ studentId: string }>();
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [changingStatus, setChangingStatus] = useState(false);

  const student = useStudent(studentId ?? null);
  const canManage = hasPermission(user?.permissions, "students.manage");
  const canViewMedical = hasPermission(
    user?.permissions,
    "students.medical.view",
  );
  const canManageMedical = hasPermission(
    user?.permissions,
    "students.medical.manage",
  );

  if (student.isPending) {
    return (
      <Page>
        <LoadingState
          label={t("students.loading")}
          testId="student-profile-loading"
        />
      </Page>
    );
  }

  if (student.isError || !student.data) {
    return (
      <Page>
        <ErrorState
          title={t("students.profile_error")}
          requestId={requestIdOf(student.error)}
          requestIdLabel={t("common.request_id")}
          retry={
            <Button variant="outline" onClick={() => void student.refetch()}>
              {t("common.retry")}
            </Button>
          }
          testId="student-profile-error"
        />
        <p className="mt-4">
          <Link className="ui-link" to="/students">
            {t("students.back_to_list")}
          </Link>
        </p>
      </Page>
    );
  }

  const detail = student.data;
  const amharicName = [
    detail.person.given_name_am,
    detail.person.father_name_am,
    detail.person.grandfather_name_am,
  ]
    .filter(Boolean)
    .join(" ");

  const overview = (
    <div className="grid gap-6 md:grid-cols-[auto_1fr]">
      <StudentPhotoCard student={detail} canManage={canManage} />
      <dl className="grid gap-3 sm:grid-cols-2" data-testid="student-overview">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.number")}
          </dt>
          <dd className="ui-num text-sm">{detail.student_number}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.status")}
          </dt>
          <dd className="text-sm">
            <Badge variant={statusVariant(detail.status)}>
              {t(`students.status.${detail.status}`)}
            </Badge>
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.date_of_birth")}
          </dt>
          <dd className="text-sm">
            {detail.person.date_of_birth ?? t("students.not_set")}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.sex")}
          </dt>
          <dd className="text-sm">
            {detail.person.sex
              ? t(`students.sex.${detail.person.sex}`)
              : t("students.not_set")}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.phone")}
          </dt>
          <dd className="text-sm">
            {detail.person.phone ?? t("students.not_set")}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.email")}
          </dt>
          <dd className="text-sm">
            {detail.person.email ?? t("students.not_set")}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.address")}
          </dt>
          <dd className="text-sm">
            {detail.person.address ?? t("students.not_set")}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.admission_date")}
          </dt>
          <dd className="text-sm">
            {detail.admission_date ?? t("students.not_set")}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.enrollment")}
          </dt>
          <dd className="text-sm">
            {detail.enrollment
              ? [detail.enrollment.level_name, detail.enrollment.section_code]
                  .filter(Boolean)
                  .join(" · ")
              : t("students.not_enrolled")}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {t("students.notes")}
          </dt>
          <dd className="text-sm whitespace-pre-line">
            {detail.notes || t("students.not_set")}
          </dd>
        </div>
      </dl>
    </div>
  );

  const enrollments =
    detail.enrollments.length === 0 ? (
      <EmptyState title={t("students.enrollments.empty")} />
    ) : (
      <div
        className="overflow-x-auto"
        tabIndex={0}
        role="region"
        aria-label={t("students.enrollments")}
      >
        <table className="ui-table" data-testid="student-enrollments">
          <thead>
            <tr>
              <th scope="col">{t("students.enrollment.year")}</th>
              <th scope="col">{t("students.enrollment.level")}</th>
              <th scope="col">{t("students.enrollment.section")}</th>
              <th scope="col">{t("students.enrollment.roll_number")}</th>
              <th scope="col">{t("students.status")}</th>
            </tr>
          </thead>
          <tbody>
            {detail.enrollments.map((enrollment) => (
              <tr key={enrollment.id}>
                <td>
                  {enrollment.year_name ??
                    enrollment.year_code ??
                    t("students.not_set")}
                </td>
                <td>
                  {enrollment.level_name ??
                    enrollment.level_code ??
                    t("students.not_set")}
                </td>
                <td>{enrollment.section_code ?? t("students.not_set")}</td>
                <td>{enrollment.roll_number ?? t("students.not_set")}</td>
                <td>{t(`students.status.${enrollment.status}`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );

  const panels = [
    { key: "overview", label: t("students.tab.overview"), content: overview },
    {
      key: "enrollments",
      label: t("students.enrollments"),
      content: enrollments,
    },
    {
      key: "guardians",
      label: t("students.guardians"),
      content: <StudentGuardians student={detail} canManage={canManage} />,
    },
    {
      key: "documents",
      label: t("students.documents"),
      content: <StudentDocuments student={detail} canManage={canManage} />,
    },
  ];
  if (canViewMedical) {
    panels.push({
      key: "medical",
      label: t("students.medical"),
      content: <StudentMedical student={detail} canManage={canManageMedical} />,
    });
  }

  return (
    <Page>
      <PageHeader
        breadcrumbs={
          <Link className="ui-link text-sm" to="/students">
            {t("students.back_to_list")}
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
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                data-testid="student-status-open"
                onClick={() => setChangingStatus(true)}
              >
                {t("students.progress.change_status")}
              </Button>
              <Button variant="outline" onClick={() => setEditing(true)}>
                {t("students.edit.open")}
              </Button>
            </div>
          ) : undefined
        }
      />

      <Card>
        <CardContent className="p-4">
          <Tabs items={panels} />
        </CardContent>
      </Card>

      {canManage ? (
        <StudentEditDialog
          student={detail}
          open={editing}
          onClose={() => {
            setEditing(false);
            void queryClient.invalidateQueries({
              queryKey: ["students", "detail", detail.id],
            });
          }}
        />
      ) : null}

      {canManage && allowedStatusActions(detail.status).length > 0 ? (
        <StudentStatusDialog
          student={detail}
          open={changingStatus}
          onClose={() => setChangingStatus(false)}
        />
      ) : null}
    </Page>
  );
}
