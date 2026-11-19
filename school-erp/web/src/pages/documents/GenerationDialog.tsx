import { ApiRequestError } from "@erp/api-client";
import { Badge, Button, Checkbox, Dialog, Field, Input, Select } from "@erp/ui-web";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { useBatch, useGenerationStudents, useGenerationTargets } from "./queries";
import type {
  GenerationStarted,
  GenerationTargetType,
  TemplateSummary,
} from "./types";

function published(templates: TemplateSummary[]): TemplateSummary[] {
  return templates.filter((template) => Boolean(template.current_version_id));
}

export function GenerationDialog({
  open,
  onClose,
  templates,
  initialTemplateId,
}: {
  open: boolean;
  onClose: () => void;
  templates: TemplateSummary[];
  initialTemplateId?: string | null;
}) {
  const { t } = useI18n();
  const choices = useMemo(() => published(templates), [templates]);
  const [templateId, setTemplateId] = useState("");
  const [targetType, setTargetType] = useState<GenerationTargetType>("student");
  const [studentSearch, setStudentSearch] = useState("");
  const [studentId, setStudentId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [combine, setCombine] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [started, setStarted] = useState<GenerationStarted | null>(null);

  const targets = useGenerationTargets(open);
  const students = useGenerationStudents(studentSearch, open && targetType === "student");
  const batch = useBatch(started?.batch_id ?? null);

  useEffect(() => {
    if (!open) return;
    setTemplateId(initialTemplateId ?? choices[0]?.id ?? "");
    setTargetType("student");
    setStudentSearch("");
    setStudentId("");
    setSectionId("");
    setLevelId("");
    setCombine(false);
    setBusy(false);
    setError(null);
    setStarted(null);
  }, [open, initialTemplateId, choices]);

  const levelName = (id: string) =>
    targets.data?.levels.find((level) => level.id === id)?.name ?? id;
  const sectionLabel = (id: string) => {
    const section = targets.data?.sections.find((item) => item.id === id);
    if (!section) return id;
    const label = levelName(section.level_id);
    return section.name ? `${label} — ${section.name}` : `${label} — ${section.code}`;
  };

  const canSubmit = Boolean(
    templateId &&
      !busy &&
      (targetType === "student"
        ? studentId
        : targetType === "section"
          ? sectionId
          : levelId),
  );

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const target =
        targetType === "student"
          ? { type: "student" as const, student_id: studentId }
          : targetType === "section"
            ? {
                type: "section" as const,
                section_id: sectionId,
                year_id: targets.data?.year?.id ?? null,
              }
            : {
                type: "level" as const,
                level_id: levelId,
                year_id: targets.data?.year?.id ?? null,
              };
      const result = await api.post<GenerationStarted>("/api/v1/documents/generation", {
        template_id: templateId,
        combine,
        target,
      });
      setStarted(result);
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("documents.generation.error"));
    } finally {
      setBusy(false);
    }
  };

  const status = batch.data?.status ?? started?.status;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("documents.generation.title")}
      description={t("documents.generation.description")}
      closeLabel={t("common.close")}
      footer={
        started ? (
          <>
            {batch.data?.download_url ? (
              <a
                className="ui-btn ui-btn--outline ui-btn--sm"
                href={batch.data.download_url}
                target="_blank"
                rel="noreferrer"
                data-testid="generation-combined-download"
              >
                {t("documents.generation.download_pack")}
              </a>
            ) : null}
            <Link className="ui-btn ui-btn--primary ui-btn--sm" to="/documents/issued">
              {t("documents.generation.view_issued")}
            </Link>
            <Button variant="outline" onClick={onClose}>
              {t("common.close")}
            </Button>
          </>
        ) : (
          <>
            <Button variant="outline" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button
              onClick={() => void submit()}
              disabled={!canSubmit}
              data-testid="generation-start"
            >
              {busy ? t("documents.generation.starting") : t("documents.generation.start")}
            </Button>
          </>
        )
      }
    >
      <div className="ui-field" data-testid="generation-dialog">
        {choices.length === 0 ? (
          <p role="alert" className="ui-help" data-testid="generation-no-templates">
            {t("documents.generation.no_templates")}
          </p>
        ) : started ? (
          <div className="space-y-3" data-testid="generation-progress">
            <p className="text-sm text-muted-foreground">
              {t("documents.generation.progress_hint", { count: started.count })}
            </p>
            <progress
              max={100}
              value={batch.data?.progress ?? 0}
              aria-label={t("documents.generation.progress")}
              className="w-full"
            />
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge variant={status === "succeeded" ? "success" : status === "failed" ? "danger" : "neutral"}>
                {t(`documents.generation.status.${status ?? "queued"}`)}
              </Badge>
              <span className="ui-num">
                {t("documents.generation.counts", {
                  issued: batch.data?.issued_count ?? 0,
                  failed: batch.data?.failed_count ?? 0,
                  total: batch.data?.count ?? started.count,
                })}
              </span>
            </div>
            {batch.data?.failure_summary ? (
              <p role="status" className="text-sm text-destructive">
                {batch.data.failure_summary}
              </p>
            ) : null}
            {status === "succeeded" ? (
              <p role="status" className="text-sm text-muted-foreground">
                {t("documents.generation.done")}
              </p>
            ) : null}
          </div>
        ) : (
          <>
            <Field label={t("documents.generation.template")} required>
              <Select
                value={templateId}
                data-testid="generation-template"
                onChange={(event) => setTemplateId(event.target.value)}
              >
                {choices.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("documents.generation.target")}>
              <Select
                value={targetType}
                data-testid="generation-target-type"
                onChange={(event) => setTargetType(event.target.value as GenerationTargetType)}
              >
                <option value="student">{t("documents.generation.target_student")}</option>
                <option value="section">{t("documents.generation.target_section")}</option>
                <option value="level">{t("documents.generation.target_level")}</option>
              </Select>
            </Field>

            {targetType === "student" ? (
              <>
                <Field label={t("documents.generation.student_search")}>
                  <Input
                    value={studentSearch}
                    onChange={(event) => setStudentSearch(event.target.value)}
                    placeholder={t("documents.generation.student_placeholder")}
                    data-testid="generation-student-search"
                  />
                </Field>
                <Field label={t("documents.generation.student")} required>
                  <Select
                    value={studentId}
                    data-testid="generation-student"
                    onChange={(event) => setStudentId(event.target.value)}
                  >
                    <option value="">{t("documents.generation.choose_student")}</option>
                    {(students.data?.items ?? []).map((student) => (
                      <option key={student.id} value={student.id}>
                        {student.student_number} — {student.full_name}
                        {student.level_name ? ` (${student.level_name})` : ""}
                      </option>
                    ))}
                  </Select>
                </Field>
                {students.isPending ? (
                  <p className="ui-help">{t("documents.generation.loading_students")}</p>
                ) : (students.data?.items.length ?? 0) === 0 ? (
                  <p className="ui-help">{t("documents.generation.no_students")}</p>
                ) : null}
              </>
            ) : targetType === "section" ? (
              <Field label={t("documents.generation.section")} required>
                <Select
                  value={sectionId}
                  data-testid="generation-section"
                  onChange={(event) => setSectionId(event.target.value)}
                >
                  <option value="">{t("documents.generation.choose_section")}</option>
                  {(targets.data?.sections ?? []).map((section) => (
                    <option key={section.id} value={section.id}>
                      {sectionLabel(section.id)}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <Field label={t("documents.generation.level")} required>
                <Select
                  value={levelId}
                  data-testid="generation-level"
                  onChange={(event) => setLevelId(event.target.value)}
                >
                  <option value="">{t("documents.generation.choose_level")}</option>
                  {(targets.data?.levels ?? []).map((level) => (
                    <option key={level.id} value={level.id}>
                      {level.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}

            {!targets.data?.year && targetType !== "student" ? (
              <p role="status" className="ui-help" data-testid="generation-no-year">
                {t("documents.generation.no_year")}
              </p>
            ) : null}

            <Checkbox
              checked={combine}
              data-testid="generation-combine"
              label={t("documents.generation.combine")}
              onChange={(event) => setCombine(event.target.checked)}
            />
            <p className="ui-help">{t("documents.generation.combine_hint")}</p>

            {error ? (
              <p role="alert" className="ui-error-text" data-testid="generation-error">
                {error}
              </p>
            ) : null}
          </>
        )}
      </div>
    </Dialog>
  );
}
