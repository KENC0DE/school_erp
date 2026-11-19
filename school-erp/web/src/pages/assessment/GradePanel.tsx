import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Select,
} from "@erp/ui-web";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import {
  ASSESSMENT,
  useAssessmentLevels,
  useAssessmentStages,
  useAssessmentSubjects,
  useAssessmentYears,
  useScaleAssessments,
  useScaleAssignments,
  useScales,
} from "./queries";
import {
  ROUNDINGS,
  SCALE_CONTEXTS,
  SCALE_TYPES,
  assignmentTargetName,
  bandTo,
  emptyScaleDraft,
  scaleBandsValid,
  scaleDraftFrom,
  splitBand,
  type BandDraft,
  type GradeScale,
  type ScaleContext,
  type ScaleDraft,
  type ScaleTestResult,
} from "./types";

interface ScalePayload {
  name: string;
  name_am: string | null;
  type: string;
  description: string | null;
  is_default: boolean;
  lower_bound: string;
  upper_bound: string;
  precision: number;
  rounding: string;
  effective_from: string | null;
  effective_to: string | null;
  is_active: boolean;
  bands: {
    min_value: string;
    max_value: string;
    label: string;
    remark: string | null;
    gpa_points: string | null;
    is_pass: boolean;
    color: string | null;
    sort_order: number;
  }[];
}

function buildScalePayload(draft: ScaleDraft): ScalePayload {
  return {
    name: draft.name,
    name_am: draft.name_am || null,
    type: draft.type,
    description: draft.description || null,
    is_default: draft.is_default,
    lower_bound: draft.lower_bound,
    upper_bound: draft.upper_bound,
    precision: Number(draft.precision),
    rounding: draft.rounding,
    effective_from: draft.effective_from || null,
    effective_to: draft.effective_to || null,
    is_active: draft.is_active,
    bands: draft.bands.map((band, index) => ({
      min_value: band.min_value,
      max_value: bandTo(draft, index),
      label: band.label,
      remark: band.remark || null,
      gpa_points: band.gpa_points || null,
      is_pass: band.is_pass,
      color: band.color || null,
      sort_order: index,
    })),
  };
}

function bandsSignature(draft: ScaleDraft): string {
  return JSON.stringify(
    buildScalePayload(draft).bands.map((band) => ({
      ...band,
      remark: band.remark ?? "",
      gpa_points: band.gpa_points ?? "",
      color: band.color ?? "",
    })),
  );
}

function scaleError(
  t: (key: string, values?: Record<string, string | number>) => string,
  error: unknown,
  fallback: string,
): string | null {
  if (!error) return null;
  return error instanceof ApiRequestError ? error.message : t(fallback);
}

export function GradePanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const scales = useScales();
  const assignments = useScaleAssignments();
  const years = useAssessmentYears();

  const [draft, setDraft] = useState<ScaleDraft>(emptyScaleDraft);
  const [original, setOriginal] = useState<ScaleDraft | null>(null);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [deleted, setDeleted] = useState<string | null>(null);

  const levelQuery = useAssessmentLevels(canManage);
  const stageQuery = useAssessmentStages(canManage);
  const subjectQuery = useAssessmentSubjects(canManage);

  const [assignmentScale, setAssignmentScale] = useState("");
  const [context, setContext] = useState<ScaleContext>("default");
  const [targetId, setTargetId] = useState("");
  const [assignmentYear, setAssignmentYear] = useState("");
  const assessmentQuery = useScaleAssessments(
    context === "assessment" ? assignmentYear || null : null,
  );

  const [testScale, setTestScale] = useState("");
  const [testValue, setTestValue] = useState("");

  const rows = scales.data?.items ?? [];
  const assignmentRows = assignments.data?.items ?? [];

  useEffect(() => {
    if (testScale || rows.length === 0) return;
    setTestScale((rows.find((row) => row.is_default) ?? rows[0]).id);
  }, [rows, testScale]);

  useEffect(() => {
    if (assignmentYear || !years.data) return;
    setAssignmentYear(years.data.current_year_id ?? years.data.items[0]?.id ?? "");
  }, [assignmentYear, years.data]);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["assessment", "scales"] });
    void queryClient.invalidateQueries({ queryKey: ["assessment", "scale-assignments"] });
  };

  const save = useMutation({
    mutationFn: (current: ScaleDraft) => {
      const payload = buildScalePayload(current);
      if (current.id !== null) {
        const changed = original !== null && bandsSignature(current) !== bandsSignature(original);
        return api.patch<GradeScale>(`${ASSESSMENT}/scales/${current.id}`, {
          row_version: current.row_version,
          ...payload,
          bands: changed ? payload.bands : undefined,
        });
      }
      return api.post<GradeScale>(`${ASSESSMENT}/scales`, payload);
    },
    onSuccess: () => {
      setEditing(false);
      setSaved(true);
      setDeleted(null);
      setDraft(emptyScaleDraft());
      setOriginal(null);
      invalidate();
    },
  });

  const remove = useMutation({
    mutationFn: (scaleId: string) => api.del(`${ASSESSMENT}/scales/${scaleId}`),
    onSuccess: (_result, scaleId) => {
      setDeleted(scaleId);
      invalidate();
    },
  });

  const assign = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(`${ASSESSMENT}/scale-assignments`, body),
    onSuccess: () => {
      setTargetId("");
      invalidate();
    },
  });

  const unassign = useMutation({
    mutationFn: (assignmentId: string) =>
      api.del(`${ASSESSMENT}/scale-assignments/${assignmentId}`),
    onSuccess: () => {
      invalidate();
    },
  });

  const test = useMutation({
    mutationFn: (body: { scaleId: string; value: string }) =>
      api.post<ScaleTestResult>(`${ASSESSMENT}/scales/${body.scaleId}/test`, {
        value: body.value,
      }),
  });

  const startNew = () => {
    save.reset();
    remove.reset();
    setSaved(false);
    setDraft(emptyScaleDraft());
    setOriginal(null);
    setEditing(true);
  };

  const startEdit = (scale: GradeScale) => {
    save.reset();
    remove.reset();
    setSaved(false);
    const next = scaleDraftFrom(scale);
    setDraft(next);
    setOriginal(next);
    setEditing(true);
  };

  const updateBand = (index: number, patch: Partial<BandDraft>) => {
    setDraft((current) => ({
      ...current,
      bands: current.bands.map((band, position) =>
        position === index ? { ...band, ...patch } : band,
      ),
    }));
  };

  const changeLower = (value: string) => {
    setDraft((current) => ({
      ...current,
      lower_bound: value,
      bands:
        current.bands.length > 0 && current.bands[0].min_value !== value
          ? current.bands.map((band, index) =>
              index === 0 ? { ...band, min_value: value } : band,
            )
          : current.bands,
    }));
  };

  const addBand = () => {
    setDraft((current) => {
      const next = splitBand(current);
      return next === null ? current : { ...current, bands: next };
    });
  };

  const removeBand = (index: number) => {
    setDraft((current) => ({
      ...current,
      bands: current.bands.filter((_, position) => position !== index),
    }));
  };

  const valid = useMemo(
    () => scaleBandsValid(draft) && /^[0-6]$/.test(draft.precision),
    [draft],
  );
  const saveError = scaleError(t, save.error, "assessment.grade.save_failed");
  const deleteError = scaleError(t, remove.error, "assessment.grade.delete_failed");
  const testError = scaleError(t, test.error, "assessment.grade.save_failed");
  const targetMissing = context !== "default" && !targetId;

  const submitAssignment = (event: FormEvent) => {
    event.preventDefault();
    if (!assignmentScale || targetMissing) return;
    assign.mutate({
      scale_id: assignmentScale,
      context,
      assessment_id: context === "assessment" ? targetId : null,
      subject_id: context === "subject" ? targetId : null,
      level_id: context === "level" ? targetId : null,
      stage_id: context === "stage" ? targetId : null,
    });
  };

  const subjectItems = subjectQuery.data?.items ?? [];
  const levelItems = levelQuery.data?.items ?? [];
  const stageItems = stageQuery.data?.items ?? [];
  const assessmentItems = assessmentQuery.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="grade-panel">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>{t("assessment.grade.title")}</CardTitle>
              <CardDescription>{t("assessment.grade.intro")}</CardDescription>
            </div>
            <div className="flex items-center gap-3">
              {saved ? (
                <p className="text-sm text-primary" role="status" data-testid="grade-saved">
                  {t("assessment.grade.saved")}
                </p>
              ) : null}
              {canManage ? (
                <Button type="button" onClick={startNew} data-testid="grade-new">
                  {t("assessment.grade.new")}
                </Button>
              ) : null}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {scales.isLoading ? (
            <LoadingState label={t("assessment.grade.loading")} testId="grade-loading" />
          ) : scales.isError ? (
            <ErrorState title={t("assessment.grade.load_error")} testId="grade-load-error" />
          ) : rows.length === 0 ? (
            <EmptyState
              title={t("assessment.grade.empty")}
              description={t("assessment.grade.empty_hint")}
              testId="grade-empty"
            />
          ) : (
            <ul className="space-y-2" data-testid="grade-list">
              {rows.map((scale) => (
                <li
                  key={scale.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3"
                  data-testid={`grade-row-${scale.id}`}
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{scale.name}</span>
                      {scale.is_default ? (
                        <Badge variant="success" data-testid={`grade-default-${scale.id}`}>
                          {t("assessment.grade.default_badge")}
                        </Badge>
                      ) : null}
                      <span className="text-xs text-muted-foreground">
                        {t("assessment.structure.version", { version: scale.version })}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground" data-testid={`grade-bands-${scale.id}`}>
                      {scale.bands
                        .map((band, index) =>
                          index === scale.bands.length - 1
                            ? `${band.min_value}–${band.max_value} ${band.label}`
                            : `${band.min_value}–<${band.max_value} ${band.label}`,
                        )
                        .join(" · ")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {canManage ? (
                      <>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => startEdit(scale)}
                          data-testid={`grade-edit-${scale.id}`}
                        >
                          {t("assessment.structure.edit")}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          disabled={remove.isPending}
                          onClick={() => {
                            setDeleted(null);
                            remove.mutate(scale.id);
                          }}
                          data-testid={`grade-delete-${scale.id}`}
                        >
                          {t("assessment.grade.delete")}
                        </Button>
                      </>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {deleted ? (
            <p className="text-sm text-muted-foreground" role="status" data-testid="grade-deleted">
              {t("assessment.grade.deleted")}
            </p>
          ) : null}
          {deleteError ? (
            <p className="text-sm text-destructive" role="alert" data-testid="grade-delete-error">
              {deleteError}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {canManage && editing ? (
        <Card>
          <CardHeader>
            <CardTitle>
              {draft.id ? t("assessment.grade.edit") : t("assessment.grade.new")}
            </CardTitle>
            <CardDescription>{t("assessment.grade.intro")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-5"
              onSubmit={(event) => {
                event.preventDefault();
                if (!valid) return;
                save.mutate(draft);
              }}
              data-testid="grade-editor"
            >
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <Field label={t("assessment.structure.name")} required>
                  <Input
                    data-testid="grade-name"
                    value={draft.name}
                    required
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, name: event.target.value }))
                    }
                  />
                </Field>
                <Field label={t("assessment.grade.type")}>
                  <Select
                    data-testid="grade-type"
                    value={draft.type}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        type: event.target.value as ScaleDraft["type"],
                      }))
                    }
                  >
                    {SCALE_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {t(`assessment.grade.type.${type}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={t("assessment.grade.precision")}>
                  <Input
                    data-testid="grade-precision"
                    type="number"
                    min={0}
                    max={6}
                    value={draft.precision}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, precision: event.target.value }))
                    }
                  />
                </Field>
                <Field label={t("assessment.grade.lower_bound")} required>
                  <Input
                    data-testid="grade-lower"
                    inputMode="decimal"
                    value={draft.lower_bound}
                    required
                    onChange={(event) => changeLower(event.target.value)}
                  />
                </Field>
                <Field label={t("assessment.grade.upper_bound")} required>
                  <Input
                    data-testid="grade-upper"
                    inputMode="decimal"
                    value={draft.upper_bound}
                    required
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, upper_bound: event.target.value }))
                    }
                  />
                </Field>
                <Field label={t("assessment.grade.rounding")}>
                  <Select
                    data-testid="grade-rounding"
                    value={draft.rounding}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        rounding: event.target.value as ScaleDraft["rounding"],
                      }))
                    }
                  >
                    {ROUNDINGS.map((rounding) => (
                      <option key={rounding} value={rounding}>
                        {t(`assessment.structure.rounding.${rounding}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={t("assessment.grade.effective_from")}>
                  <Input
                    data-testid="grade-effective-from"
                    type="date"
                    value={draft.effective_from}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        effective_from: event.target.value,
                      }))
                    }
                  />
                </Field>
                <Field label={t("assessment.grade.effective_to")}>
                  <Input
                    data-testid="grade-effective-to"
                    type="date"
                    value={draft.effective_to}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, effective_to: event.target.value }))
                    }
                  />
                </Field>
                <div className="flex items-end gap-4 pb-2">
                  <Checkbox
                    data-testid="grade-default"
                    label={t("assessment.grade.default")}
                    checked={draft.is_default}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        is_default: event.target.checked,
                      }))
                    }
                  />
                  <Checkbox
                    data-testid="grade-active"
                    label={t("assessment.structure.active")}
                    checked={draft.is_active}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, is_active: event.target.checked }))
                    }
                  />
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">{t("assessment.grade.bands")}</p>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={splitBand(draft) === null}
                    onClick={addBand}
                    data-testid="grade-add-band"
                  >
                    {t("assessment.grade.add_band")}
                  </Button>
                </div>

                {!valid ? (
                  <p className="text-sm text-destructive" role="alert" data-testid="grade-invalid">
                    {t("assessment.grade.invalid")}
                  </p>
                ) : null}

                <div className="space-y-3" data-testid="grade-bands">
                  {draft.bands.map((band, index) => {
                    const last = index === draft.bands.length - 1;
                    return (
                      <div
                        key={`${band.id ?? "new"}-${index}`}
                        className="rounded-md border border-border p-3"
                        data-testid={`grade-band-${index}`}
                      >
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                          <Field label={t("assessment.grade.band_from")} required>
                            <Input
                              data-testid={`grade-band-from-${index}`}
                              inputMode="decimal"
                              value={band.min_value}
                              required
                              onChange={(event) =>
                                updateBand(index, { min_value: event.target.value })
                              }
                            />
                          </Field>
                          <Field
                            label={t(
                              last
                                ? "assessment.grade.band_to_inclusive"
                                : "assessment.grade.band_to",
                            )}
                          >
                            <Input
                              data-testid={`grade-band-to-${index}`}
                              value={bandTo(draft, index)}
                              readOnly
                            />
                          </Field>
                          <Field label={t("assessment.grade.band_label")} required>
                            <Input
                              data-testid={`grade-band-label-${index}`}
                              value={band.label}
                              required
                              onChange={(event) =>
                                updateBand(index, { label: event.target.value })
                              }
                            />
                          </Field>
                          <Field label={t("assessment.grade.band_gpa")}>
                            <Input
                              data-testid={`grade-band-gpa-${index}`}
                              inputMode="decimal"
                              value={band.gpa_points}
                              onChange={(event) =>
                                updateBand(index, { gpa_points: event.target.value })
                              }
                            />
                          </Field>
                          <Field label={t("assessment.grade.band_remark")}>
                            <Input
                              data-testid={`grade-band-remark-${index}`}
                              value={band.remark}
                              onChange={(event) =>
                                updateBand(index, { remark: event.target.value })
                              }
                            />
                          </Field>
                          <Field label={t("assessment.grade.band_color")}>
                            <Input
                              data-testid={`grade-band-color-${index}`}
                              value={band.color}
                              onChange={(event) =>
                                updateBand(index, { color: event.target.value })
                              }
                            />
                          </Field>
                          <div className="flex items-end gap-3 pb-2">
                            <Checkbox
                              data-testid={`grade-band-pass-${index}`}
                              label={t("assessment.grade.band_pass")}
                              checked={band.is_pass}
                              onChange={(event) =>
                                updateBand(index, { is_pass: event.target.checked })
                              }
                            />
                          </div>
                          <div className="flex items-end pb-1">
                            <Button
                              type="button"
                              variant="outline"
                              disabled={draft.bands.length <= 1}
                              onClick={() => removeBand(index)}
                              data-testid={`grade-band-remove-${index}`}
                            >
                              {t("assessment.grade.remove_band")}
                            </Button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {saveError ? (
                <p className="text-sm text-destructive" role="alert" data-testid="grade-error">
                  {saveError}
                </p>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={save.isPending || !valid} data-testid="grade-save">
                  {save.isPending ? t("assessment.grade.saving") : t("assessment.grade.save")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setEditing(false);
                    setDraft(emptyScaleDraft());
                    setOriginal(null);
                  }}
                >
                  {t("assessment.grade.cancel")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("assessment.grade.test")}</CardTitle>
          <CardDescription>{t("assessment.grade.test_hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("assessment.grade.assignment_scale")} className="max-w-xs">
              <Select
                data-testid="grade-test-scale"
                value={testScale}
                onChange={(event) => {
                  setTestScale(event.target.value);
                  test.reset();
                }}
              >
                {rows.map((scale) => (
                  <option key={scale.id} value={scale.id}>
                    {scale.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("assessment.grade.test_value")}>
              <Input
                data-testid="grade-test-value"
                inputMode="decimal"
                value={testValue}
                onChange={(event) => setTestValue(event.target.value)}
              />
            </Field>
            <Button
              type="button"
              disabled={!testScale || !testValue.trim() || test.isPending}
              onClick={() => test.mutate({ scaleId: testScale, value: testValue })}
              data-testid="grade-test-run"
            >
              {t("assessment.grade.test")}
            </Button>
          </div>
          {test.data ? (
            <p className="text-sm" role="status" data-testid="grade-test-result">
              {t("assessment.grade.test_result", {
                value: test.data.value,
                label: test.data.label,
              })}
            </p>
          ) : null}
          {testError ? (
            <p className="text-sm text-destructive" role="alert" data-testid="grade-test-error">
              {testError}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("assessment.grade.assignment")}</CardTitle>
          <CardDescription>{t("assessment.grade.assignment_hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {canManage ? (
            <form className="flex flex-wrap items-end gap-3" onSubmit={submitAssignment}>
              <Field label={t("assessment.grade.assignment_scale")} className="max-w-xs">
                <Select
                  data-testid="assignment-scale"
                  value={assignmentScale}
                  required
                  onChange={(event) => setAssignmentScale(event.target.value)}
                >
                  <option value="">—</option>
                  {rows.map((scale) => (
                    <option key={scale.id} value={scale.id}>
                      {scale.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t("assessment.grade.context")} className="max-w-xs">
                <Select
                  data-testid="assignment-context"
                  value={context}
                  onChange={(event) => {
                    setContext(event.target.value as ScaleContext);
                    setTargetId("");
                  }}
                >
                  {SCALE_CONTEXTS.map((item) => (
                    <option key={item} value={item}>
                      {t(`assessment.grade.context.${item}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              {context === "assessment" ? (
                <Field label={t("assessment.grade.assignment_year")} className="max-w-xs">
                  <Select
                    data-testid="assignment-year"
                    value={assignmentYear}
                    onChange={(event) => {
                      setAssignmentYear(event.target.value);
                      setTargetId("");
                    }}
                  >
                    {(years.data?.items ?? []).map((year) => (
                      <option key={year.id} value={year.id}>
                        {year.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
              {context === "assessment" ? (
                <Field label={t("assessment.grade.assignment_assessment")} className="max-w-xs">
                  <Select
                    data-testid="assignment-assessment"
                    value={targetId}
                    required
                    onChange={(event) => setTargetId(event.target.value)}
                  >
                    <option value="">—</option>
                    {assessmentItems.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.title}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
              {context === "subject" ? (
                <Field label={t("assessment.structure.subject")} className="max-w-xs">
                  <Select
                    data-testid="assignment-subject"
                    value={targetId}
                    required
                    onChange={(event) => setTargetId(event.target.value)}
                  >
                    <option value="">—</option>
                    {subjectItems.map((subject) => (
                      <option key={subject.id} value={subject.id}>
                        {subject.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
              {context === "level" ? (
                <Field label={t("assessment.structure.level")} className="max-w-xs">
                  <Select
                    data-testid="assignment-level"
                    value={targetId}
                    required
                    onChange={(event) => setTargetId(event.target.value)}
                  >
                    <option value="">—</option>
                    {levelItems.map((level) => (
                      <option key={level.id} value={level.id}>
                        {level.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
              {context === "stage" ? (
                <Field label={t("assessment.structure.stage")} className="max-w-xs">
                  <Select
                    data-testid="assignment-stage"
                    value={targetId}
                    required
                    onChange={(event) => setTargetId(event.target.value)}
                  >
                    <option value="">—</option>
                    {stageItems.map((stage) => (
                      <option key={stage.id} value={stage.id}>
                        {stage.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : null}
              <Button
                type="submit"
                disabled={assign.isPending || !assignmentScale || targetMissing}
                data-testid="assignment-add"
              >
                {t("assessment.grade.assignment_add")}
              </Button>
            </form>
          ) : null}

          {assignments.isLoading ? (
            <LoadingState label={t("assessment.grade.loading")} testId="assignment-loading" />
          ) : assignments.isError ? (
            <ErrorState title={t("assessment.grade.load_error")} testId="assignment-load-error" />
          ) : assignmentRows.length === 0 ? (
            <EmptyState
              title={t("assessment.grade.assignment_empty")}
              description={t("assessment.grade.assignment_hint")}
              testId="assignment-empty"
            />
          ) : (
            <ul className="space-y-2" data-testid="assignment-list">
              {assignmentRows.map((assignment) => (
                <li
                  key={assignment.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3"
                  data-testid={`assignment-row-${assignment.id}`}
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge>{t(`assessment.grade.context.${assignment.context}`)}</Badge>
                      <span className="font-medium">{assignment.scale_name}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {assignmentTargetName(assignment) ?? t("assessment.grade.context.default")}
                    </p>
                  </div>
                  {canManage ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={unassign.isPending}
                      onClick={() => unassign.mutate(assignment.id)}
                      data-testid={`assignment-remove-${assignment.id}`}
                    >
                      {t("assessment.grade.assignment_remove")}
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {scaleError(t, unassign.error, "assessment.grade.assignment_delete_failed") ? (
            <p className="text-sm text-destructive" role="alert" data-testid="assignment-error">
              {scaleError(t, unassign.error, "assessment.grade.assignment_delete_failed")}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
