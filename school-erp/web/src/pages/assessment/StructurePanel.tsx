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
  useStructures,
} from "./queries";
import {
  AGGREGATIONS,
  ROUNDINGS,
  SCOPE_TYPES,
  YEAR_MODES,
  componentsTotal,
  draftFrom,
  emptyComponent,
  emptyDraft,
  fromMicro,
  toMicro,
  type ComponentDraft,
  type Structure,
  type StructureDraft,
  type YearMode,
} from "./types";

function scopeName(t: (key: string) => string, structure: Structure): string {
  if (structure.scope_type === "level") {
    return `${t("assessment.structure.level")}: ${structure.level_name ?? structure.scope_key}`;
  }
  if (structure.scope_type === "stage") {
    return `${t("assessment.structure.stage")}: ${structure.stage_name ?? structure.scope_key}`;
  }
  if (structure.scope_type === "subject") {
    return `${t("assessment.structure.subject")}: ${structure.subject_name ?? structure.scope_key}`;
  }
  return t("assessment.structure.school");
}

function percentWidth(value: string, intended: string): number {
  const total = toMicro(value);
  const target = toMicro(intended);
  if (total === null || target === null || target === 0n) return 0;
  return Number((total * 100n) / target);
}

function buildPayload(draft: StructureDraft): Record<string, unknown> {
  return {
    scope_type: draft.scope_type,
    level_id: draft.scope_type === "level" ? draft.level_id : null,
    stage_id: draft.scope_type === "stage" ? draft.stage_id : null,
    subject_id: draft.scope_type === "subject" ? draft.subject_id : null,
    name: draft.name,
    name_am: draft.name_am || null,
    year_mode: draft.year_mode,
    year_weights:
      draft.year_mode === "weighted_average" ? draft.year_weights.map((weight) => weight || "0") : null,
    precision: Number(draft.precision),
    rounding: draft.rounding,
    intended_total: draft.intended_total.trim() || null,
    descriptive_mode: draft.descriptive_mode,
    components: draft.components.map((component, index) => ({
      id: component.id,
      key: component.key,
      name: component.name,
      name_am: component.name_am || null,
      max_points: component.max_points,
      aggregation: component.aggregation,
      absent_counts_as_zero: component.absent_zero,
      best_n: component.aggregation === "best_n" ? Number(component.best_n || 0) : null,
      cap: component.aggregation === "sum_capped" ? component.cap : null,
      sort_order: index,
      is_active: component.is_active,
    })),
  };
}

export function StructurePanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const years = useAssessmentYears();
  const [yearId, setYearId] = useState("");
  const structures = useStructures(yearId || null);
  const [draft, setDraft] = useState<StructureDraft>(emptyDraft);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);

  const levelQuery = useAssessmentLevels(canManage);
  const stageQuery = useAssessmentStages(canManage);
  const subjectQuery = useAssessmentSubjects(canManage);

  const year = years.data?.items.find((item) => item.id === yearId) ?? null;

  useEffect(() => {
    if (yearId || !years.data) return;
    setYearId(years.data.current_year_id ?? years.data.items[0]?.id ?? "");
  }, [yearId, years.data]);

  const changeYear = (next: string) => {
    setYearId(next);
    setDraft(emptyDraft());
    setEditing(false);
    setSaved(false);
    save.reset();
  };

  const totalMicro = useMemo(() => componentsTotal(draft.components), [draft.components]);
  const intendedMicro = draft.intended_total.trim() ? toMicro(draft.intended_total) : null;
  const invalidIntended = draft.intended_total.trim() !== "" && intendedMicro === null;
  const mismatch =
    totalMicro !== null &&
    intendedMicro !== null &&
    intendedMicro > 0n &&
    totalMicro !== intendedMicro;
  const over = totalMicro !== null && intendedMicro !== null && totalMicro > intendedMicro;
  const componentsInvalid = draft.components.some((component) => {
    const maxPoints = toMicro(component.max_points);
    return (
      !component.key.trim() ||
      !component.name.trim() ||
      maxPoints === null ||
      maxPoints <= 0n ||
      (component.aggregation === "best_n" && !component.best_n.trim()) ||
      (component.aggregation === "sum_capped" && toMicro(component.cap) === null)
    );
  });

  const save = useMutation({
    mutationFn: (current: StructureDraft) => {
      const body = buildPayload(current);
      if (current.id !== null) {
        return api.patch(`${ASSESSMENT}/structures/${current.id}`, {
          ...body,
          row_version: current.row_version,
        });
      }
      return api.post(`${ASSESSMENT}/structures`, { year_id: yearId, ...body });
    },
    onSuccess: () => {
      setEditing(false);
      setSaved(true);
      setDraft(emptyDraft());
      void queryClient.invalidateQueries({ queryKey: ["assessment", "structures"] });
    },
  });

  const startNew = () => {
    setSaved(false);
    save.reset();
    setDraft(emptyDraft());
    setEditing(true);
  };

  const startEdit = (structure: Structure) => {
    setSaved(false);
    save.reset();
    setDraft(draftFrom(structure));
    setEditing(true);
  };

  const updateComponent = (index: number, patch: Partial<ComponentDraft>) => {
    setDraft((current) => ({
      ...current,
      components: current.components.map((component, position) =>
        position === index ? { ...component, ...patch } : component,
      ),
    }));
  };

  const addComponent = () => {
    setDraft((current) => {
      const used = new Set(current.components.map((component) => component.key));
      let number = current.components.length + 1;
      while (used.has(`component_${number}`)) number += 1;
      const component = {
        ...emptyComponent(current.components.length),
        key: `component_${number}`,
      };
      return { ...current, components: [...current.components, component] };
    });
  };

  const removeComponent = (index: number) => {
    setDraft((current) => ({
      ...current,
      components: current.components.filter((_, position) => position !== index),
    }));
  };

  const setYearMode = (mode: YearMode) => {
    setDraft((current) => ({
      ...current,
      year_mode: mode,
      year_weights:
        mode === "weighted_average"
          ? current.year_weights.length > 0
            ? current.year_weights
            : (year?.terms ?? []).map(() => "")
          : [],
    }));
  };

  const targetMissing =
    (draft.scope_type === "level" && !draft.level_id) ||
    (draft.scope_type === "stage" && !draft.stage_id) ||
    (draft.scope_type === "subject" && !draft.subject_id);
  const weightsMissing =
    draft.year_mode === "weighted_average" &&
    (draft.year_weights.length === 0 ||
      draft.year_weights.some((weight) => weight.trim() === "" || toMicro(weight) === null));
  const saveDisabled =
    save.isPending ||
    !draft.name.trim() ||
    targetMissing ||
    weightsMissing ||
    invalidIntended ||
    componentsInvalid ||
    totalMicro === null ||
    draft.components.length === 0 ||
    over;

  const rows = structures.data?.items ?? [];
  const error =
    save.error instanceof ApiRequestError ? save.error.message : save.error ? t("assessment.structure.save_failed") : null;

  return (
    <div className="space-y-4" data-testid="structure-panel">
      <Card>
        <CardHeader>
          <CardTitle>{t("assessment.structure.title")}</CardTitle>
          <CardDescription>{t("assessment.structure.intro")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("assessment.structure.year")} className="max-w-xs">
              <Select
                data-testid="structure-year"
                value={yearId}
                onChange={(event) => changeYear(event.target.value)}
              >
                {(years.data?.items ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
            {canManage ? (
              <Button type="button" onClick={startNew} data-testid="structure-new">
                {t("assessment.structure.new")}
              </Button>
            ) : null}
            {saved ? (
              <p className="text-sm text-primary" role="status" data-testid="structure-saved">
                {t("assessment.structure.saved")}
              </p>
            ) : null}
          </div>

          {structures.isLoading ? (
            <LoadingState label={t("assessment.structure.loading")} testId="structure-loading" />
          ) : structures.isError ? (
            <ErrorState title={t("assessment.structure.load_error")} testId="structure-load-error" />
          ) : rows.length === 0 ? (
            <EmptyState
              title={t("assessment.structure.empty")}
              description={t("assessment.structure.empty_hint")}
              testId="structure-empty"
            />
          ) : (
            <ul className="space-y-2" data-testid="structure-list">
              {rows.map((structure) => (
                <li
                  key={structure.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3"
                  data-testid={`structure-row-${structure.id}`}
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{structure.name}</span>
                      <Badge variant={structure.is_active ? "success" : "neutral"}>
                        {structure.is_active ? t("assessment.structure.active") : t("assessment.structure.inactive")}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {t("assessment.structure.version", { version: structure.version })}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {scopeName(t, structure)} · {t("assessment.structure.total", { total: structure.total })} /{" "}
                      {structure.intended_total ?? "—"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className="text-xs text-muted-foreground"
                      data-testid={`structure-match-${structure.id}`}
                    >
                      {structure.total_matches ? "" : t("assessment.structure.total_warning", {
                        total: structure.total,
                        intended: structure.intended_total ?? "—",
                      })}
                    </span>
                    {canManage ? (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => startEdit(structure)}
                        data-testid={`structure-edit-${structure.id}`}
                      >
                        {t("assessment.structure.edit")}
                      </Button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {canManage && editing ? (
        <Card>
          <CardHeader>
            <CardTitle>{draft.id ? t("assessment.structure.edit") : t("assessment.structure.new")}</CardTitle>
            <CardDescription>{t("assessment.structure.intro")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-5"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                save.mutate(draft);
              }}
            >
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <Field label={t("assessment.structure.name")} required>
                  <Input
                    data-testid="structure-name"
                    value={draft.name}
                    required
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, name: event.target.value }))
                    }
                  />
                </Field>
                <Field label={t("assessment.structure.scope")}>
                  <Select
                    data-testid="structure-scope-type"
                    value={draft.scope_type}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        scope_type: event.target.value as StructureDraft["scope_type"],
                      }))
                    }
                  >
                    {SCOPE_TYPES.map((scope) => (
                      <option key={scope} value={scope}>
                        {t(`assessment.structure.${scope}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
                {draft.scope_type === "level" ? (
                  <Field label={t("assessment.structure.level")} required>
                    <Select
                      data-testid="structure-level"
                      value={draft.level_id}
                      required
                      onChange={(event) =>
                        setDraft((current) => ({ ...current, level_id: event.target.value }))
                      }
                    >
                      <option value="">—</option>
                      {(levelQuery.data?.items ?? []).map((level) => (
                        <option key={level.id} value={level.id}>
                          {level.name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                ) : null}
                {draft.scope_type === "stage" ? (
                  <Field label={t("assessment.structure.stage")} required>
                    <Select
                      data-testid="structure-stage"
                      value={draft.stage_id}
                      required
                      onChange={(event) =>
                        setDraft((current) => ({ ...current, stage_id: event.target.value }))
                      }
                    >
                      <option value="">—</option>
                      {(stageQuery.data?.items ?? []).map((stage) => (
                        <option key={stage.id} value={stage.id}>
                          {stage.name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                ) : null}
                {draft.scope_type === "subject" ? (
                  <Field label={t("assessment.structure.subject")} required>
                    <Select
                      data-testid="structure-subject"
                      value={draft.subject_id}
                      required
                      onChange={(event) =>
                        setDraft((current) => ({ ...current, subject_id: event.target.value }))
                      }
                    >
                      <option value="">—</option>
                      {(subjectQuery.data?.items ?? []).map((subject) => (
                        <option key={subject.id} value={subject.id}>
                          {subject.name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                ) : null}
                <Field label={t("assessment.structure.term_system")}>
                  <Input value={year?.term_system ?? ""} readOnly />
                </Field>
                <Field label={t("assessment.structure.year_rule")}>
                  <Select
                    data-testid="structure-year-mode"
                    value={draft.year_mode}
                    onChange={(event) => setYearMode(event.target.value as YearMode)}
                  >
                    {YEAR_MODES.map((mode) => (
                      <option key={mode} value={mode}>
                        {t(`assessment.structure.year_mode.${mode}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={t("assessment.structure.rounding")}>
                  <Select
                    data-testid="structure-rounding"
                    value={draft.rounding}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        rounding: event.target.value as StructureDraft["rounding"],
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
                <Field label={t("assessment.structure.precision")}>
                  <Input
                    data-testid="structure-precision"
                    type="number"
                    min={0}
                    max={6}
                    value={draft.precision}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, precision: event.target.value }))
                    }
                  />
                </Field>
                <Field label={t("assessment.structure.intended_total")}>
                  <Input
                    data-testid="structure-intended-total"
                    inputMode="decimal"
                    value={draft.intended_total}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, intended_total: event.target.value }))
                    }
                  />
                </Field>
                <div className="flex items-end pb-2">
                  <Checkbox
                    data-testid="structure-descriptive"
                    label={t("assessment.structure.descriptive")}
                    checked={draft.descriptive_mode}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        descriptive_mode: event.target.checked,
                      }))
                    }
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">{t("assessment.structure.descriptive_help")}</p>

              {draft.year_mode === "weighted_average" ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium">{t("assessment.structure.year_weights")}</p>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {(year?.terms ?? []).map((term, index) => (
                      <Field key={term.id} label={term.name}>
                        <Input
                          data-testid={`structure-weight-${index}`}
                          inputMode="decimal"
                          value={draft.year_weights[index] ?? ""}
                          onChange={(event) =>
                            setDraft((current) => {
                              const weights = [...current.year_weights];
                              weights[index] = event.target.value;
                              return { ...current, year_weights: weights };
                            })
                          }
                        />
                      </Field>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">{t("assessment.structure.components")}</p>
                  <div className="flex items-center gap-3">
                    {totalMicro !== null ? (
                      <p className="text-sm" data-testid="structure-total">
                        {t("assessment.structure.total", { total: fromMicro(totalMicro) })}
                      </p>
                    ) : null}
                    <Button type="button" variant="outline" onClick={addComponent} data-testid="component-add">
                      {t("assessment.structure.add_component")}
                    </Button>
                  </div>
                </div>

                {mismatch && totalMicro !== null ? (
                  <p className="text-sm text-destructive" role="alert" data-testid="structure-total-warning">
                    {t("assessment.structure.total_warning", {
                      total: fromMicro(totalMicro),
                      intended: intendedMicro === null ? "—" : fromMicro(intendedMicro),
                    })}
                  </p>
                ) : null}

                <div className="space-y-3" data-testid="structure-components">
                  {draft.components.map((component, index) => {
                    const width =
                      draft.intended_total.trim() && totalMicro !== null
                        ? percentWidth(component.max_points, draft.intended_total)
                        : 0;
                    return (
                      <div
                        key={`${component.id ?? "new"}-${index}`}
                        className="rounded-md border border-border p-3"
                        data-testid={`component-row-${index}`}
                      >
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                          <Field label={t("assessment.structure.component_key")} required>
                            <Input
                              data-testid={`component-key-${index}`}
                              value={component.key}
                              required
                              onChange={(event) =>
                                updateComponent(index, { key: event.target.value })
                              }
                            />
                          </Field>
                          <Field label={t("assessment.structure.component_name")} required>
                            <Input
                              data-testid={`component-name-${index}`}
                              value={component.name}
                              required
                              onChange={(event) =>
                                updateComponent(index, { name: event.target.value })
                              }
                            />
                          </Field>
                          <Field label={t("assessment.structure.max_points")} required>
                            <Input
                              data-testid={`component-max-${index}`}
                              inputMode="decimal"
                              value={component.max_points}
                              required
                              onChange={(event) =>
                                updateComponent(index, { max_points: event.target.value })
                              }
                            />
                          </Field>
                          <Field label={t("assessment.structure.aggregation")}>
                            <Select
                              data-testid={`component-aggregation-${index}`}
                              value={component.aggregation}
                              onChange={(event) =>
                                updateComponent(index, {
                                  aggregation: event.target.value as ComponentDraft["aggregation"],
                                })
                              }
                            >
                              {AGGREGATIONS.map((aggregation) => (
                                <option key={aggregation} value={aggregation}>
                                  {t(`assessment.structure.aggregation.${aggregation}`)}
                                </option>
                              ))}
                            </Select>
                          </Field>
                          {component.aggregation === "best_n" ? (
                            <Field label={t("assessment.structure.best_n")} required>
                              <Input
                                data-testid={`component-best-n-${index}`}
                                type="number"
                                min={1}
                                value={component.best_n}
                                required
                                onChange={(event) =>
                                  updateComponent(index, { best_n: event.target.value })
                                }
                              />
                            </Field>
                          ) : null}
                          {component.aggregation === "sum_capped" ? (
                            <Field label={t("assessment.structure.cap")} required>
                              <Input
                                data-testid={`component-cap-${index}`}
                                inputMode="decimal"
                                value={component.cap}
                                required
                                onChange={(event) =>
                                  updateComponent(index, { cap: event.target.value })
                                }
                              />
                            </Field>
                          ) : null}
                          <div className="flex items-end gap-2 pb-2">
                            <Checkbox
                              data-testid={`component-absent-${index}`}
                              label={t("assessment.structure.absent_zero")}
                              checked={component.absent_zero}
                              onChange={(event) =>
                                updateComponent(index, { absent_zero: event.target.checked })
                              }
                            />
                          </div>
                          <div className="flex items-end pb-1">
                            <Button
                              type="button"
                              variant="outline"
                              disabled={draft.components.length <= 1}
                              onClick={() => removeComponent(index)}
                              data-testid={`component-remove-${index}`}
                            >
                              {t("assessment.structure.remove_component")}
                            </Button>
                          </div>
                        </div>
                        {draft.intended_total.trim() ? (
                          <div
                            className="mt-2 h-1 rounded bg-muted"
                            aria-hidden="true"
                          >
                            <div
                              className="h-1 rounded bg-primary"
                              style={{ width: `${Math.min(100, width)}%` }}
                            />
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>

              {error ? (
                <p className="text-sm text-destructive" role="alert" data-testid="structure-error">
                  {error}
                </p>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={saveDisabled} data-testid="structure-save">
                  {save.isPending ? t("assessment.structure.saving") : t("assessment.structure.save")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setEditing(false);
                    setDraft(emptyDraft());
                  }}
                >
                  {t("assessment.structure.cancel")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
