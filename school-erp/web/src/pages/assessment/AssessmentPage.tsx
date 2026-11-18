import { Page, PageHeader } from "@erp/ui-web";

import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { StructurePanel } from "./StructurePanel";

export function AssessmentPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];
  const allowed = permissions.includes("assessment.view");
  const canManage = permissions.includes("assessment.manage");

  if (!allowed) {
    return (
      <Page>
        <PageHeader title={t("assessment.title")} description={t("assessment.intro")} />
        <p role="alert" className="text-sm text-destructive" data-testid="assessment-permission">
          {t("error.permission_denied")}
        </p>
      </Page>
    );
  }

  return (
    <Page>
      <div className="space-y-5" data-testid="assessment-page">
        <PageHeader title={t("assessment.title")} description={t("assessment.intro")} />
        <StructurePanel canManage={canManage} />
      </div>
    </Page>
  );
}
