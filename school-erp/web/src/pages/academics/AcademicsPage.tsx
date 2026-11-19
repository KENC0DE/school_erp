import { useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/Card";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { CurriculumPanel } from "./CurriculumPanel";
import { ScopePanel } from "./ScopePanel";
import { SectionsPanel } from "./SectionsPanel";
import { SubjectsPanel } from "./SubjectsPanel";
import { YearsPanel } from "./YearsPanel";
import { can, useProfiles, useScope, useSections, useSubjects, useYears } from "./queries";
import type { Panel } from "./types";

const TABS: Panel[] = ["setup", "scope", "curriculum", "years", "subjects", "sections"];

interface SetupStep {
  panel: Exclude<Panel, "setup">;
  done: boolean;
}

function SetupChecklist({
  canManage,
  onOpen,
}: {
  canManage: boolean;
  onOpen: (panel: Panel) => void;
}) {
  const { t } = useI18n();
  const scope = useScope();
  const profiles = useProfiles();
  const years = useYears();
  const subjects = useSubjects();
  const sections = useSections(null);

  const steps: SetupStep[] = [
    {
      panel: "scope",
      done: Boolean(scope.data && scope.data.level_count > 0),
    },
    {
      panel: "curriculum",
      done: (profiles.data?.items ?? []).length > 0,
    },
    {
      panel: "years",
      done: (years.data?.items ?? []).some((year) => year.status === "open"),
    },
    {
      panel: "subjects",
      done: (subjects.data?.items ?? []).length > 0,
    },
    {
      panel: "sections",
      done: (sections.data?.items ?? []).length > 0,
    },
  ];
  const done = steps.filter((step) => step.done).length;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle>{t("academics.setup.title")}</CardTitle>
            <CardDescription>{t("academics.setup.intro")}</CardDescription>
          </div>
          <Badge data-testid="setup-progress">
            {t("academics.setup.progress", { done, total: steps.length })}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <ol className="space-y-2" data-testid="setup-checklist">
          {steps.map((step, index) => (
            <li
              key={step.panel}
              data-testid={`setup-step-${step.panel}`}
              data-done={step.done ? "true" : "false"}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium">
                  {index + 1}. {t(`academics.setup.step.${step.panel}`)}
                </p>
                <p className="text-xs text-muted-foreground">{t(`academics.setup.step.${step.panel}_hint`)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge>{t(step.done ? "academics.setup.status.done" : "academics.setup.status.pending")}</Badge>
                <Button variant="outline" onClick={() => onOpen(step.panel)}>
                  {t("academics.setup.open")}
                </Button>
              </div>
            </li>
          ))}
        </ol>
        {!canManage ? (
          <p className="text-sm text-muted-foreground">{t("academics.setup.manage_hint")}</p>
        ) : null}
        {done === steps.length ? (
          <p className="text-sm text-primary" data-testid="setup-complete">
            {t("academics.setup.complete")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function AcademicsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const permissionSet = user?.permissions ?? [];
  const allowed = can(permissionSet, "academics.view");
  const canManage = can(permissionSet, "academics.manage");
  const [panel, setPanel] = useState<Panel>("setup");

  if (!allowed) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("academics.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p role="alert" className="text-sm text-destructive" data-testid="academics-permission">
            {t("academics.permission_denied")}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5" data-testid="academics-page">
      <div>
        <h1 className="text-2xl font-semibold">{t("academics.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("academics.intro")}</p>
      </div>

      <div role="tablist" aria-label={t("academics.title")} className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <Button
            key={tab}
            role="tab"
            variant={panel === tab ? "default" : "outline"}
            aria-selected={panel === tab}
            data-testid={`academics-tab-${tab}`}
            onClick={() => setPanel(tab)}
          >
            {t(`academics.tab.${tab}`)}
          </Button>
        ))}
      </div>

      {panel === "setup" ? <SetupChecklist canManage={canManage} onOpen={setPanel} /> : null}
      {panel === "scope" ? <ScopePanel canManage={canManage} /> : null}
      {panel === "curriculum" ? <CurriculumPanel canManage={canManage} /> : null}
      {panel === "years" ? <YearsPanel canManage={canManage} /> : null}
      {panel === "subjects" ? <SubjectsPanel canManage={canManage} /> : null}
      {panel === "sections" ? <SectionsPanel canManage={canManage} /> : null}
    </div>
  );
}
