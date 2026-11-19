import { Page, PageHeader, Button } from "@erp/ui-web";
import { useState } from "react";

import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { ApprovalsPanel } from "./ApprovalsPanel";
import { AssessmentDashboardPanel } from "./AssessmentDashboardPanel";
import { GradePanel } from "./GradePanel";
import { MarkEntryPanel } from "./MarkEntryPanel";
import { StructurePanel } from "./StructurePanel";

type Panel = "structure" | "marks" | "grades" | "approvals" | "dashboard";

const PANELS: Panel[] = [
  "structure",
  "marks",
  "grades",
  "approvals",
  "dashboard",
];

export function AssessmentPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];
  const can = (permission: string) =>
    permissions.includes("*") || permissions.includes(permission);
  const allowed = can("assessment.view");
  const canManage = can("assessment.manage");
  const canEnter = can("assessment.enter_marks");
  const canCorrect = can("assessment.correct");
  const canApprove = can("assessment.approve");
  const canPublish = can("assessment.publish");
  const [panel, setPanel] = useState<Panel>("structure");

  if (!allowed) {
    return (
      <Page>
        <PageHeader
          title={t("assessment.title")}
          description={t("assessment.intro")}
        />
        <p
          role="alert"
          className="text-sm text-destructive"
          data-testid="assessment-permission"
        >
          {t("error.permission_denied")}
        </p>
      </Page>
    );
  }

  return (
    <Page>
      <div className="space-y-5" data-testid="assessment-page">
        <PageHeader
          title={t("assessment.title")}
          description={t("assessment.intro")}
        />
        <div
          role="tablist"
          aria-label={t("assessment.title")}
          className="flex flex-wrap gap-2"
        >
          {PANELS.map((item) => (
            <Button
              key={item}
              role="tab"
              variant={panel === item ? "default" : "outline"}
              aria-selected={panel === item}
              data-testid={`assessment-tab-${item}`}
              onClick={() => setPanel(item)}
            >
              {t(`assessment.tab.${item}`)}
            </Button>
          ))}
        </div>
        {panel === "structure" ? (
          <StructurePanel canManage={canManage} />
        ) : null}
        {panel === "marks" ? (
          <MarkEntryPanel canEnter={canEnter} canCorrect={canCorrect} />
        ) : null}
        {panel === "grades" ? <GradePanel canManage={canManage} /> : null}
        {panel === "approvals" ? (
          <ApprovalsPanel canApprove={canApprove} canPublish={canPublish} />
        ) : null}
        {panel === "dashboard" ? (
          <AssessmentDashboardPanel canManage={canManage} />
        ) : null}
      </div>
    </Page>
  );
}
