import { ApiRequestError } from "@erp/api-client";
import { useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Select,
  Textarea,
} from "@erp/ui-web";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { MarkGrid, type MarkCell } from "./MarkGrid";
import {
  STATUS_SHORT,
  buildTemplate,
  cellKey,
  parseUpload,
  type CellValue,
  type MarkColumn,
  type MarkRow,
  type UploadCell,
  type UploadPreview,
} from "./marks";
import {
  ASSESSMENT,
  useAssessmentYears,
  useMarkAssessments,
  useMarkSheets,
  useMarkSubmission,
  useMarkWindows,
} from "./queries";
import {
  SCORE_STATUSES,
  type ScoreBulkResult,
  type ScoreSheet,
  type ScoreStatus,
} from "./types";

const SAVE_DELAY = 800;

interface MarkEntryPanelProps {
  canEnter: boolean;
  canCorrect: boolean;
}

function baseCells(sheets: ScoreSheet[]): Record<string, MarkCell> {
  const cells: Record<string, MarkCell> = {};
  for (const sheet of sheets) {
    for (const item of sheet.items) {
      const key = cellKey(sheet.assessment_id, item.student_id);
      cells[key] = {
        raw: item.raw_score ?? "",
        status: item.status,
        version: item.row_version,
        scoreId: item.score_id,
        converted: item.converted,
        savedRaw: item.raw_score ?? "",
        savedStatus: item.status,
        pending: false,
        saving: false,
        error: null,
        conflict: false,
      };
    }
  }
  return cells;
}

function uniqueBy<T>(items: T[], key: (item: T) => string): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (const item of items) {
    const value = key(item);
    if (seen.has(value)) continue;
    seen.add(value);
    result.push(item);
  }
  return result;
}

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

export function MarkEntryPanel({ canEnter, canCorrect }: MarkEntryPanelProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const years = useAssessmentYears();
  const [yearId, setYearId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [termId, setTermId] = useState("");

  const assessments = useMarkAssessments(yearId || null);
  const items = useMemo(
    () => assessments.data?.items ?? [],
    [assessments.data],
  );
  const scoped = useMemo(
    () => items.filter((item) => item.year_id === yearId),
    [items, yearId],
  );

  const sectionRows = useMemo(
    () => uniqueBy(scoped, (item) => item.section_id),
    [scoped],
  );
  const subjectRows = useMemo(
    () =>
      uniqueBy(
        scoped.filter((item) => item.section_id === sectionId),
        (item) => item.subject_id,
      ),
    [scoped, sectionId],
  );
  const termRows = useMemo(
    () =>
      uniqueBy(
        scoped.filter(
          (item) =>
            item.section_id === sectionId && item.subject_id === subjectId,
        ),
        (item) => item.term_id,
      ),
    [scoped, sectionId, subjectId],
  );

  const columns = useMemo<MarkColumn[]>(
    () =>
      scoped
        .filter(
          (item) =>
            item.section_id === sectionId &&
            item.subject_id === subjectId &&
            item.term_id === termId,
        )
        .sort(
          (left, right) =>
            left.assessment_date.localeCompare(right.assessment_date) ||
            left.component_name.localeCompare(right.component_name),
        )
        .map((item) => ({
          id: item.id,
          title: item.title,
          outOf: item.out_of,
          componentMax: item.component_max_points,
          allowBonus: item.allow_bonus,
        })),
    [scoped, sectionId, subjectId, termId],
  );
  const columnIds = useMemo(
    () => columns.map((column) => column.id),
    [columns],
  );
  const columnMap = useMemo(
    () => new Map(columns.map((column) => [column.id, column])),
    [columns],
  );

  const sheets = useMarkSheets(columnIds);
  const windows = useMarkWindows(yearId || null, sectionId || null);
  const submissionQuery = useMarkSubmission(
    yearId || null,
    sectionId || null,
    subjectId || null,
  );

  const [cells, setCells] = useState<Record<string, MarkCell>>({});
  const [hydratedSignature, setHydratedSignature] = useState<string | null>(
    null,
  );
  const [pasteNotice, setPasteNotice] = useState(0);
  const [conflict, setConflict] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadName, setUploadName] = useState<string | null>(null);
  const [preview, setPreview] = useState<UploadPreview | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionStudent, setCorrectionStudent] = useState("");
  const [correctionAssessment, setCorrectionAssessment] = useState("");
  const [correctionRaw, setCorrectionRaw] = useState("");
  const [correctionStatus, setCorrectionStatus] =
    useState<ScoreStatus>("present");
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionMessage, setCorrectionMessage] = useState<string | null>(
    null,
  );
  const [correctionError, setCorrectionError] = useState<string | null>(null);

  const cellsRef = useRef(cells);
  const latestRef = useRef<Record<string, CellValue>>({});
  const columnMapRef = useRef(columnMap);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const inFlight = useRef(new Map<string, string>());
  const focusedRef = useRef<{ assessmentId: string; studentId: string } | null>(
    null,
  );

  useEffect(() => {
    cellsRef.current = cells;
  }, [cells]);

  useEffect(() => {
    columnMapRef.current = columnMap;
  }, [columnMap]);

  useEffect(
    () => () => {
      for (const timer of timers.current.values()) clearTimeout(timer);
      timers.current.clear();
    },
    [],
  );

  useEffect(() => {
    if (yearId || !years.data) return;
    setYearId(years.data.current_year_id ?? years.data.items[0]?.id ?? "");
  }, [years.data, yearId]);

  useEffect(() => {
    if (!assessments.data || !yearId) return;
    const available = items.filter((item) => item.year_id === yearId);
    if (available.length === 0) return;

    const currentSection = available.some(
      (item) => item.section_id === sectionId,
    )
      ? sectionId
      : available[0].section_id;
    if (currentSection !== sectionId) {
      setSectionId(currentSection);
      return;
    }

    const sectionItems = available.filter(
      (item) => item.section_id === currentSection,
    );
    const currentSubject = sectionItems.some(
      (item) => item.subject_id === subjectId,
    )
      ? subjectId
      : (sectionItems[0]?.subject_id ?? "");
    if (currentSubject !== subjectId) {
      setSubjectId(currentSubject);
      return;
    }

    const subjectItems = sectionItems.filter(
      (item) => item.subject_id === currentSubject,
    );
    if (subjectItems.some((item) => item.term_id === termId)) return;
    const currentTerm = years.data?.items.find(
      (year) => year.id === yearId,
    )?.current_term_id;
    setTermId(
      subjectItems.find((item) => item.term_id === currentTerm)?.term_id ??
        subjectItems[0]?.term_id ??
        "",
    );
  }, [
    assessments.data,
    items,
    sectionId,
    subjectId,
    termId,
    yearId,
    years.data,
  ]);

  useEffect(() => {
    if (!sheets.data) return;
    const incoming = baseCells(sheets.data);
    setHydratedSignature(
      sheets.data.map((sheet) => sheet.assessment_id).join("|"),
    );
    setCells((previous) => {
      const next = { ...incoming };
      for (const [key, cell] of Object.entries(previous)) {
        if ((cell.pending || cell.saving || cell.error) && incoming[key]) {
          next[key] = {
            ...incoming[key],
            raw: cell.raw,
            status: cell.status,
            pending: cell.pending,
            saving: cell.saving,
            error: cell.error,
            conflict: cell.conflict,
          };
        }
      }
      return next;
    });
  }, [sheets.data]);

  const rows = useMemo<MarkRow[]>(() => {
    if (!sheets.data) return [];
    const found = new Map<string, MarkRow>();
    for (const sheet of sheets.data) {
      for (const item of sheet.items) {
        if (found.has(item.student_id)) continue;
        found.set(item.student_id, {
          studentId: item.student_id,
          studentNumber: item.student_number,
          studentName: item.student_name,
          rollNumber: item.roll_number,
        });
      }
    }
    return [...found.values()].sort(
      (left, right) =>
        (left.rollNumber ?? "").localeCompare(
          right.rollNumber ?? "",
          undefined,
          {
            numeric: true,
          },
        ) || left.studentNumber.localeCompare(right.studentNumber),
    );
  }, [sheets.data]);

  const submission = useMemo(() => {
    const list = submissionQuery.data?.items ?? [];
    return list.find((item) => item.term_id === termId) ?? null;
  }, [submissionQuery.data, termId]);

  const termWindows = useMemo(() => {
    const levelId =
      scoped.find((item) => item.section_id === sectionId)?.level_id ?? null;
    return (windows.data?.items ?? []).filter(
      (window) =>
        window.term_id === termId &&
        (window.section_id === sectionId ||
          (window.section_id === null && window.level_id === levelId)),
    );
  }, [windows.data, termId, sectionId, scoped]);

  const archived = sheets.data?.some((sheet) => !sheet.editable) ?? false;
  let readOnlyReason: string | null = null;
  if (!canEnter) readOnlyReason = "assessment.marks.readonly.permission";
  else if (archived) readOnlyReason = "assessment.marks.readonly.archived";
  else if (submission !== null && submission.status !== "draft") {
    readOnlyReason = `assessment.marks.readonly.${submission.status}`;
  } else if (
    termWindows.length > 0 &&
    !termWindows.some((window) => window.state === "open")
  ) {
    readOnlyReason = "assessment.marks.readonly.window";
  }
  const readOnly = readOnlyReason !== null;
  const locked = submission?.status === "locked";

  const sheetSignature = useMemo(
    () =>
      sheets.data
        ? sheets.data.map((sheet) => sheet.assessment_id).join("|")
        : "",
    [sheets.data],
  );

  const clearTimer = (key: string) => {
    const timer = timers.current.get(key);
    if (timer !== undefined) clearTimeout(timer);
    timers.current.delete(key);
  };

  const persist = async (
    assessmentId: string,
    studentId: string,
    value: CellValue,
  ) => {
    const key = cellKey(assessmentId, studentId);
    clearTimer(key);
    const current = cellsRef.current[key];
    if (!current) return;
    const isPresent = value.status === "present";
    const raw = isPresent ? value.raw.trim() : "";

    if (isPresent && raw === "" && current.scoreId === null) {
      setCells((previous) =>
        previous[key]
          ? {
              ...previous,
              [key]: {
                ...previous[key],
                raw: "",
                status: "present",
                pending: false,
                saving: false,
                error: null,
                conflict: false,
              },
            }
          : previous,
      );
      return;
    }
    if (raw === current.savedRaw && value.status === current.savedStatus) {
      setCells((previous) =>
        previous[key]
          ? {
              ...previous,
              [key]: {
                ...previous[key],
                pending: false,
                saving: false,
                error: null,
              },
            }
          : previous,
      );
      return;
    }

    setCells((previous) =>
      previous[key]
        ? {
            ...previous,
            [key]: {
              ...previous[key],
              pending: false,
              saving: true,
              error: null,
              conflict: false,
            },
          }
        : previous,
    );

    const signature = `${value.status}:${raw}`;
    if (inFlight.current.get(key) === signature) return;
    inFlight.current.set(key, signature);

    try {
      const result = await api.put<ScoreBulkResult>(
        `${ASSESSMENT}/assessments/${assessmentId}/scores`,
        {
          items: [
            {
              student_id: studentId,
              raw_score: isPresent && raw !== "" ? raw : null,
              status: value.status,
              row_version: current.version,
            },
          ],
        },
      );
      const item = result.sheet.items.find(
        (entry) => entry.student_id === studentId,
      );
      const savedRaw = isPresent ? raw : "";
      latestRef.current[key] = { raw: savedRaw, status: value.status };
      setCells((previous) => {
        if (!previous[key]) return previous;
        return {
          ...previous,
          [key]: {
            ...previous[key],
            raw: savedRaw,
            status: value.status,
            pending: false,
            saving: false,
            error: null,
            conflict: false,
            version: item?.row_version ?? previous[key].version,
            scoreId: item?.score_id ?? previous[key].scoreId,
            converted: item?.converted ?? null,
            savedRaw,
            savedStatus: value.status,
          },
        };
      });
      setSaveError(null);
    } catch (error) {
      const stale = error instanceof ApiRequestError && error.status === 409;
      const message =
        error instanceof ApiRequestError
          ? error.message
          : t("assessment.marks.save_failed");
      setCells((previous) =>
        previous[key]
          ? {
              ...previous,
              [key]: {
                ...previous[key],
                pending: false,
                saving: false,
                error: message,
                conflict: stale,
              },
            }
          : previous,
      );
      if (stale) setConflict(true);
      else setSaveError(message);
    } finally {
      if (inFlight.current.get(key) === signature) inFlight.current.delete(key);
    }
  };

  const changeCell = (
    assessmentId: string,
    studentId: string,
    value: CellValue,
  ) => {
    const key = cellKey(assessmentId, studentId);
    latestRef.current[key] = value;
    setCells((previous) => {
      if (!previous[key]) return previous;
      return {
        ...previous,
        [key]: {
          ...previous[key],
          raw: value.raw,
          status: value.status,
          pending: true,
          error: null,
          conflict: false,
        },
      };
    });
    clearTimer(key);
    timers.current.set(
      key,
      setTimeout(() => {
        void persist(assessmentId, studentId, value);
      }, SAVE_DELAY),
    );
  };

  const saveNow = (assessmentId: string, studentId: string) => {
    const key = cellKey(assessmentId, studentId);
    const value =
      latestRef.current[key] ??
      (cellsRef.current[key]
        ? {
            raw: cellsRef.current[key].raw,
            status: cellsRef.current[key].status,
          }
        : null);
    if (value === null) return;
    void persist(assessmentId, studentId, value);
  };

  const revertCell = (assessmentId: string, studentId: string) => {
    const key = cellKey(assessmentId, studentId);
    clearTimer(key);
    delete latestRef.current[key];
    setCells((previous) => {
      if (!previous[key]) return previous;
      return {
        ...previous,
        [key]: {
          ...previous[key],
          raw: previous[key].savedRaw,
          status: previous[key].savedStatus,
          pending: false,
          saving: false,
          error: null,
          conflict: false,
        },
      };
    });
  };

  const flushDirty = () => {
    for (const [key, value] of Object.entries(latestRef.current)) {
      const separator = key.indexOf(":");
      const assessmentId = key.slice(0, separator);
      const studentId = key.slice(separator + 1);
      void persist(assessmentId, studentId, value);
    }
  };

  const reloadMarks = () => {
    setConflict(false);
    setSaveError(null);
    latestRef.current = {};
    setCells({});
    void queryClient.invalidateQueries({
      queryKey: ["assessment", "mark-sheets"],
    });
  };

  const valueOf = (assessmentId: string, studentId: string): string => {
    const cell = cellsRef.current[cellKey(assessmentId, studentId)];
    if (!cell) return "";
    if (cell.status === "present") return cell.raw;
    return STATUS_SHORT[cell.status];
  };

  const downloadTemplate = () => {
    const text = buildTemplate(rows, columns, valueOf);
    if (typeof URL.createObjectURL !== "function") return;
    const blob = new Blob([text], { type: "text/tab-separated-values" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `marks-${sectionId}-${subjectId}.tsv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const openUpload = (file: File) => {
    setUploadError(null);
    setUploadResult(null);
    setUploadName(file.name);
    void readFile(file)
      .then((text) => {
        setPreview(
          parseUpload(
            text,
            rows,
            columns,
            (assessmentId) =>
              columnMapRef.current.get(assessmentId)?.allowBonus ?? false,
          ),
        );
        setUploadOpen(true);
      })
      .catch(() => {
        setUploadError(t("assessment.marks.upload_failed"));
        setUploadOpen(true);
      });
  };

  const applyUpload = async () => {
    if (!preview) return;
    setUploading(true);
    setUploadError(null);
    try {
      const groups = new Map<string, UploadCell[]>();
      for (const cell of preview.cells) {
        const group = groups.get(cell.assessmentId);
        if (group) group.push(cell);
        else groups.set(cell.assessmentId, [cell]);
      }
      for (const [assessmentId, group] of groups) {
        const body = {
          items: group.map((cell) => ({
            student_id: cell.studentId,
            raw_score: cell.status === "present" ? cell.raw : null,
            status: cell.status,
            row_version:
              cellsRef.current[cellKey(assessmentId, cell.studentId)]
                ?.version ?? null,
          })),
        };
        const result = await api.put<ScoreBulkResult>(
          `${ASSESSMENT}/assessments/${assessmentId}/scores`,
          body,
        );
        const byStudent = new Map(
          result.sheet.items.map((item) => [item.student_id, item]),
        );
        setCells((previous) => {
          const next = { ...previous };
          for (const cell of group) {
            const key = cellKey(assessmentId, cell.studentId);
            const item = byStudent.get(cell.studentId);
            const savedRaw = cell.status === "present" ? cell.raw : "";
            latestRef.current[key] = { raw: savedRaw, status: cell.status };
            next[key] = {
              raw: savedRaw,
              status: cell.status,
              version: item?.row_version ?? null,
              scoreId: item?.score_id ?? null,
              converted: item?.converted ?? null,
              savedRaw,
              savedStatus: cell.status,
              pending: false,
              saving: false,
              error: null,
              conflict: false,
            };
          }
          return next;
        });
      }
      setUploadOpen(false);
      setPreview(null);
      setUploadName(null);
      setUploadResult(t("assessment.marks.upload_applied"));
    } catch (error) {
      setUploadError(
        error instanceof ApiRequestError
          ? error.message
          : t("assessment.marks.upload_failed"),
      );
    } finally {
      setUploading(false);
    }
  };

  const startCorrection = () => {
    const focused = focusedRef.current;
    const fallback =
      rows[0] && columns[0]
        ? { assessmentId: columns[0].id, studentId: rows[0].studentId }
        : null;
    const target = focused ?? fallback;
    if (target === null) return;
    const cell =
      cellsRef.current[cellKey(target.assessmentId, target.studentId)];
    setCorrectionAssessment(target.assessmentId);
    setCorrectionStudent(target.studentId);
    setCorrectionRaw(cell?.raw ?? "");
    setCorrectionStatus(cell?.status ?? "present");
    setCorrectionReason("");
    setCorrectionError(null);
    setCorrectionMessage(null);
    setCorrectionOpen(true);
  };

  const submitCorrection = async () => {
    setCorrectionError(null);
    const cell =
      cellsRef.current[cellKey(correctionAssessment, correctionStudent)];
    if (!cell?.scoreId) {
      setCorrectionError(t("assessment.marks.correction_failed"));
      return;
    }
    try {
      await api.post(`${ASSESSMENT}/corrections`, {
        score_id: cell.scoreId,
        new_raw: correctionStatus === "present" ? correctionRaw || null : null,
        new_status: correctionStatus,
        reason: correctionReason,
      });
      setCorrectionOpen(false);
      setCorrectionMessage(t("assessment.marks.correction_sent"));
    } catch (error) {
      setCorrectionError(
        error instanceof ApiRequestError
          ? error.message
          : t("assessment.marks.correction_failed"),
      );
    }
  };

  const loading =
    assessments.isLoading ||
    (columnIds.length > 0 && sheets.isLoading) ||
    (Boolean(sheets.data) && hydratedSignature !== sheetSignature);
  const failed = assessments.isError || sheets.isError;

  return (
    <div className="space-y-4" data-testid="mark-entry-panel">
      <Card>
        <CardHeader>
          <CardTitle>{t("assessment.marks.title")}</CardTitle>
          <CardDescription>{t("assessment.marks.legend")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label={t("assessment.marks.year")}>
              <Select
                data-testid="mark-year"
                value={yearId}
                onChange={(event) => {
                  setYearId(event.target.value);
                  setSectionId("");
                  setSubjectId("");
                  setTermId("");
                }}
              >
                {(years.data?.items ?? []).map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("assessment.marks.section")}>
              <Select
                data-testid="mark-section"
                value={sectionId}
                onChange={(event) => {
                  setSectionId(event.target.value);
                  setSubjectId("");
                  setTermId("");
                }}
              >
                {sectionRows.map((item) => (
                  <option key={item.section_id} value={item.section_id}>
                    {item.level_name} {item.section_code}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("assessment.marks.subject")}>
              <Select
                data-testid="mark-subject"
                value={subjectId}
                onChange={(event) => {
                  setSubjectId(event.target.value);
                  setTermId("");
                }}
              >
                {subjectRows.map((item) => (
                  <option key={item.subject_id} value={item.subject_id}>
                    {item.subject_name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("assessment.marks.term")}>
              <Select
                data-testid="mark-term"
                value={termId}
                onChange={(event) => setTermId(event.target.value)}
              >
                {termRows.map((item) => (
                  <option key={item.term_id} value={item.term_id}>
                    {item.term_name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={rows.length === 0 || columns.length === 0}
              onClick={downloadTemplate}
              data-testid="mark-download"
            >
              {t("assessment.marks.download_template")}
            </Button>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm font-medium">
              {t("assessment.marks.upload")}
              <input
                type="file"
                className="sr-only"
                accept=".tsv,.csv,.txt,text/tab-separated-values,text/csv"
                data-testid="mark-upload-input"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) openUpload(file);
                  event.target.value = "";
                }}
              />
            </label>
            {locked && canCorrect ? (
              <Button
                type="button"
                variant="outline"
                onClick={startCorrection}
                data-testid="mark-correction-open"
              >
                {t("assessment.marks.correction")}
              </Button>
            ) : null}
            {conflict ? (
              <Button
                type="button"
                onClick={reloadMarks}
                data-testid="mark-reload"
              >
                {t("assessment.marks.reload")}
              </Button>
            ) : null}
          </div>

          {conflict ? (
            <p
              role="alert"
              className="text-sm text-destructive"
              data-testid="mark-conflict"
            >
              {t("assessment.marks.conflict")}
            </p>
          ) : null}
          {saveError ? (
            <p
              role="alert"
              className="text-sm text-destructive"
              data-testid="mark-save-error"
            >
              {saveError}
            </p>
          ) : null}
          {readOnlyReason ? (
            <p
              role="status"
              className="text-sm text-muted-foreground"
              data-testid="mark-readonly"
            >
              {t(readOnlyReason)}
            </p>
          ) : null}
          {pasteNotice > 0 ? (
            <p
              role="status"
              className="text-sm text-destructive"
              data-testid="mark-paste-issues"
            >
              {t("assessment.marks.paste_skipped", { count: pasteNotice })}
            </p>
          ) : null}
          {uploadResult ? (
            <p
              role="status"
              className="text-sm text-primary"
              data-testid="mark-upload-result"
            >
              {uploadResult}
            </p>
          ) : null}
          {correctionMessage ? (
            <p
              role="status"
              className="text-sm text-primary"
              data-testid="mark-correction-result"
            >
              {correctionMessage}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 pt-5">
          {!yearId ? (
            <EmptyState
              title={t("assessment.marks.no_selection")}
              description={t("assessment.marks.empty_hint")}
              testId="mark-no-selection"
            />
          ) : loading ? (
            <LoadingState
              label={t("assessment.marks.loading")}
              testId="mark-loading"
            />
          ) : failed ? (
            <ErrorState
              title={t("assessment.marks.load_error")}
              testId="mark-load-error"
            />
          ) : columns.length === 0 ? (
            <EmptyState
              title={t("assessment.marks.empty")}
              description={t("assessment.marks.empty_hint")}
              testId="mark-empty"
            />
          ) : rows.length === 0 && sheets.data && !sheets.isFetching ? (
            <EmptyState
              title={t("assessment.marks.empty")}
              description={t("assessment.marks.empty_hint")}
              testId="mark-empty"
            />
          ) : (
            <MarkGrid
              rows={rows}
              columns={columns}
              cells={cells}
              readOnly={readOnly}
              precision={2}
              onChange={changeCell}
              onSaveNow={saveNow}
              onRevert={revertCell}
              onPasteIssues={(count) => {
                setPasteNotice(count);
                flushDirty();
              }}
              onFocusCell={(assessmentId, studentId) => {
                focusedRef.current = { assessmentId, studentId };
              }}
            />
          )}
        </CardContent>
      </Card>

      <Dialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title={t("assessment.marks.upload_title")}
        description={t("assessment.marks.upload_hint")}
        closeLabel={t("assessment.marks.cancel")}
        footer={
          <>
            <Button variant="outline" onClick={() => setUploadOpen(false)}>
              {t("assessment.marks.cancel")}
            </Button>
            <Button
              onClick={() => void applyUpload()}
              loading={uploading}
              disabled={!preview || preview.cells.length === 0}
              data-testid="mark-upload-apply"
            >
              {t("assessment.marks.upload_apply")}
            </Button>
          </>
        }
      >
        <div className="space-y-3" data-testid="mark-upload-preview">
          {uploadName ? (
            <p className="text-sm text-muted-foreground">{uploadName}</p>
          ) : null}
          {preview ? (
            <>
              <p className="text-sm" data-testid="mark-upload-valid">
                {t("assessment.marks.upload_valid", {
                  cells: preview.cells.length,
                  students: preview.matchedStudents,
                })}
              </p>
              {preview.issues.length > 0 ? (
                <>
                  <p
                    className="text-sm text-destructive"
                    data-testid="mark-upload-issues"
                  >
                    {t("assessment.marks.upload_issues", {
                      count: preview.issues.length,
                    })}
                  </p>
                  <ul className="max-h-56 space-y-1 overflow-y-auto text-xs">
                    {preview.issues.slice(0, 30).map((issue, index) => (
                      <li key={`${issue.code}-${issue.line}-${index}`}>
                        {t("assessment.marks.upload_line", {
                          line: issue.line,
                        })}{" "}
                        · {t(`assessment.marks.issue.${issue.code}`)} ·{" "}
                        {issue.value}
                        {issue.student ? ` · ${issue.student}` : ""}
                        {issue.assessment ? ` · ${issue.assessment}` : ""}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </>
          ) : null}
          {uploadError ? (
            <p role="alert" className="text-sm text-destructive">
              {uploadError}
            </p>
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={correctionOpen}
        onClose={() => setCorrectionOpen(false)}
        title={t("assessment.marks.correction_title")}
        description={t("assessment.marks.correction_hint")}
        closeLabel={t("assessment.marks.cancel")}
        footer={
          <>
            <Button variant="outline" onClick={() => setCorrectionOpen(false)}>
              {t("assessment.marks.cancel")}
            </Button>
            <Button
              onClick={() => void submitCorrection()}
              disabled={!correctionReason.trim()}
              data-testid="mark-correction-submit"
            >
              {t("assessment.marks.correction_submit")}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Field label={t("assessment.marks.correction_assessment")}>
            <Select
              data-testid="mark-correction-assessment"
              value={correctionAssessment}
              onChange={(event) => setCorrectionAssessment(event.target.value)}
            >
              {columns.map((column) => (
                <option key={column.id} value={column.id}>
                  {column.title}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("assessment.marks.correction_student")}>
            <Select
              data-testid="mark-correction-student"
              value={correctionStudent}
              onChange={(event) => setCorrectionStudent(event.target.value)}
            >
              {rows.map((row) => (
                <option key={row.studentId} value={row.studentId}>
                  {row.studentName}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("assessment.marks.correction_status")}>
            <Select
              data-testid="mark-correction-status"
              value={correctionStatus}
              onChange={(event) =>
                setCorrectionStatus(event.target.value as ScoreStatus)
              }
            >
              {SCORE_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {t(`assessment.marks.status.${status}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("assessment.marks.correction_value")}>
            <Input
              data-testid="mark-correction-value"
              inputMode="decimal"
              value={correctionRaw}
              disabled={correctionStatus !== "present"}
              onChange={(event) => setCorrectionRaw(event.target.value)}
            />
          </Field>
          <Field label={t("assessment.marks.correction_reason")} required>
            <Textarea
              data-testid="mark-correction-reason"
              value={correctionReason}
              onChange={(event) => setCorrectionReason(event.target.value)}
            />
          </Field>
          {correctionError ? (
            <p
              role="alert"
              className="text-sm text-destructive"
              data-testid="mark-correction-error"
            >
              {correctionError}
            </p>
          ) : null}
        </div>
      </Dialog>
    </div>
  );
}
