import { useLocalSearchParams } from "expo-router";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentRef,
} from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  getAssessment,
  getScoreSheet,
  listSubmissions,
  listWindows,
} from "../../../src/assessment/api";
import {
  assessmentErrorKey,
  hasPermission,
  syncTone,
} from "../../../src/assessment/errors";
import {
  displayConverted,
  isChanged,
  isOverMax,
  markKey,
  nextRowIndex,
  parseMarkInput,
  requestValue,
} from "../../../src/assessment/marks";
import {
  discardMarks,
  flushOutbox,
  loadOutbox,
  queueMarks,
  saveOrQueue,
  type PendingMark,
} from "../../../src/assessment/outbox";
import { loadSnapshot, saveSnapshot } from "../../../src/assessment/snapshot";
import {
  STATUS_SHORT,
  SCORE_STATUSES,
  draftFrom,
  sortScoreItems,
  type AssessmentSummary,
  type MarkDraft,
  type MarkMode,
  type MarkingWindow,
  type ScoreItem,
  type ScoreSheet,
  type ScoreStatus,
  type Submission,
  type SyncState,
} from "../../../src/assessment/types";
import { useApp } from "../../../src/context/AppContext";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import { SessionError } from "../../../src/session/session";
import { useSchoolThemeContext } from "../../../src/theme/SchoolThemeContext";
import {
  Badge,
  Button,
  Card,
  Divider,
  EmptyState,
  ErrorState,
  Field,
  Muted,
  PageHeader,
  Screen,
  Segmented,
  SectionTitle,
  type Palette,
} from "../../../src/ui";

type Translate = (
  key: string,
  values?: Record<string, string | number>,
) => string;

const SHORT_STATUS: Record<ScoreStatus, string> = {
  present: "P",
  absent: STATUS_SHORT.absent,
  excused: STATUS_SHORT.excused,
  exempt: STATUS_SHORT.exempt,
  not_taken: STATUS_SHORT.not_taken,
};

function syncedState(keys: Set<string>): Record<string, SyncState> {
  const next: Record<string, SyncState> = {};
  for (const key of keys) next[key] = "pending";
  return next;
}

function MarkRow({
  colors,
  t,
  item,
  draft,
  converted,
  overMax,
  state,
  readOnly,
  compact,
  inputRef,
  onChangeText,
  onBlur,
  onSubmit,
  onStatus,
}: {
  colors: Palette;
  t: Translate;
  item: ScoreItem;
  draft: MarkDraft;
  converted: string | null;
  overMax: boolean;
  state: SyncState | undefined;
  readOnly: boolean;
  compact: boolean;
  inputRef: (node: ComponentRef<typeof TextInput> | null) => void;
  onChangeText: (text: string) => void;
  onBlur: () => void;
  onSubmit: () => void;
  onStatus: (status: ScoreStatus) => void;
}) {
  return (
    <View
      style={[styles.row, compact ? styles.rowCompact : styles.rowCard]}
      testID={`mark-row-${item.student_id}`}
    >
      <View style={styles.rowHeader}>
        <View style={styles.nameBlock}>
          <Text style={[styles.studentName, { color: colors.foreground }]}>
            {item.student_name}
          </Text>
          <Muted colors={colors}>
            {item.roll_number
              ? `${t("assessment.marks.roll")} ${item.roll_number}`
              : item.student_number}
          </Muted>
        </View>
        {state ? (
          <View testID={`mark-sync-${item.student_id}`}>
            <Badge colors={colors} tone={syncTone(state)}>
              {t(`assessment.mobile.sync.${state}`)}
            </Badge>
          </View>
        ) : null}
      </View>

      <View style={styles.inputRow}>
        <View style={styles.inputBlock}>
          <Field
            colors={colors}
            label={t("assessment.mobile.mark")}
            value={draft.status === "present" ? draft.raw : ""}
            placeholder={t("assessment.mobile.mark_hint", {
              outOf: item.out_of,
            })}
            onChangeText={onChangeText}
            onBlur={onBlur}
            onSubmitEditing={onSubmit}
            keyboardType="decimal-pad"
            inputMode="decimal"
            returnKeyType="next"
            blurOnSubmit={false}
            editable={!readOnly}
            inputRef={inputRef}
            testID={`mark-input-${item.student_id}`}
          />
        </View>
        <View style={styles.convertedBlock}>
          <Text
            style={[styles.convertedLabel, { color: colors.mutedForeground }]}
          >
            {t("assessment.mobile.converted")}
          </Text>
          <Text
            testID={`mark-converted-${item.student_id}`}
            style={[styles.convertedValue, { color: colors.foreground }]}
          >
            {converted ?? "—"}
          </Text>
        </View>
      </View>

      {overMax ? (
        <Text style={[styles.overMax, { color: colors.destructive }]}>
          {t("assessment.mobile.over_max", { outOf: item.out_of })}
        </Text>
      ) : null}

      <Segmented
        colors={colors}
        items={SCORE_STATUSES.map((status) => ({
          key: status,
          label: compact
            ? SHORT_STATUS[status]
            : t(`assessment.marks.status.${status}`),
          active: draft.status === status,
          testID: `mark-status-${item.student_id}-${status}`,
          onPress: () => onStatus(status),
        }))}
      />
    </View>
  );
}

export default function MarkEntryScreen() {
  const params = useLocalSearchParams<{ assessmentId?: string }>();
  const assessmentId =
    typeof params.assessmentId === "string" ? params.assessmentId : "";
  const { profile, user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canEnter = hasPermission(user?.permissions, "assessment.enter_marks");

  const [assessment, setAssessment] = useState<AssessmentSummary | null>(null);
  const [sheet, setSheet] = useState<ScoreSheet | null>(null);
  const [windows, setWindows] = useState<MarkingWindow[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [drafts, setDrafts] = useState<Record<string, MarkDraft>>({});
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [sync, setSync] = useState<Record<string, SyncState>>({});
  const [pendingMarks, setPendingMarks] = useState<PendingMark[]>([]);
  const [conflictKeys, setConflictKeys] = useState<string[]>([]);
  const [mode, setMode] = useState<MarkMode>("card");
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const draftsRef = useRef(drafts);
  const dirtyRef = useRef(dirty);
  const pendingRef = useRef(pendingMarks);
  const inputs = useRef<Record<string, ComponentRef<typeof TextInput> | null>>(
    {},
  );

  useEffect(() => {
    draftsRef.current = drafts;
  }, [drafts]);
  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);
  useEffect(() => {
    pendingRef.current = pendingMarks;
  }, [pendingMarks]);

  const hydrate = useCallback(
    (
      summary: AssessmentSummary,
      nextSheet: ScoreSheet,
      nextWindows: MarkingWindow[],
      nextSubmissions: Submission[],
      keep: Set<string>,
    ) => {
      setAssessment(summary);
      setSheet(nextSheet);
      setWindows(nextWindows);
      setSubmissions(nextSubmissions);
      const previous = draftsRef.current;
      const next: Record<string, MarkDraft> = {};
      for (const item of nextSheet.items) {
        const kept = previous[item.student_id];
        next[item.student_id] =
          keep.has(item.student_id) && kept ? kept : draftFrom(item);
      }
      setDrafts(next);
    },
    [],
  );

  const refreshOutbox = useCallback(async (): Promise<PendingMark[]> => {
    if (!profile) return [];
    const entries = (await loadOutbox(profile.instanceId)).filter(
      (entry) => entry.assessment_id === assessmentId,
    );
    setPendingMarks(entries);
    return entries;
  }, [assessmentId, profile?.instanceId]);

  const load = useCallback(async () => {
    if (!profile || !assessmentId) return;
    setLoading(true);
    setErrorKey(null);
    try {
      const summary = await getAssessment(profile.instanceId, assessmentId);
      const [scores, windowList, submissionList] = await Promise.all([
        getScoreSheet(profile.instanceId, assessmentId),
        listWindows(profile.instanceId, summary.year_id, summary.section_id),
        listSubmissions(profile.instanceId, {
          year_id: summary.year_id,
          term_id: summary.term_id,
          section_id: summary.section_id,
          subject_id: summary.subject_id,
        }),
      ]);
      const entries = await refreshOutbox();
      setOffline(false);
      hydrate(
        summary,
        scores,
        windowList.items,
        submissionList.items,
        new Set(),
      );
      if (entries.length > 0) {
        setSync(syncedState(new Set(entries.map((entry) => entry.student_id))));
      }
      await saveSnapshot(profile.instanceId, {
        assessment: summary,
        sheet: scores,
        windows: windowList.items,
        submissions: submissionList.items,
      }).catch(() => undefined);
    } catch (caught) {
      if (caught instanceof SessionError && caught.code === "NETWORK_ERROR") {
        const cached = await loadSnapshot(
          profile.instanceId,
          assessmentId,
        ).catch(() => null);
        if (cached) {
          const entries = await refreshOutbox();
          hydrate(
            cached.assessment,
            cached.sheet,
            cached.windows,
            cached.submissions,
            new Set(),
          );
          setOffline(true);
          setMessage(t("assessment.mobile.offline_mode"));
          if (entries.length > 0) {
            setSync(
              syncedState(new Set(entries.map((entry) => entry.student_id))),
            );
          }
        } else {
          setErrorKey(
            assessmentErrorKey(caught, "assessment.mobile.load_error"),
          );
        }
      } else {
        setErrorKey(assessmentErrorKey(caught, "assessment.mobile.load_error"));
      }
    } finally {
      setLoading(false);
    }
  }, [assessmentId, hydrate, profile?.instanceId, refreshOutbox, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(
    () => (sheet ? sortScoreItems(sheet.items) : []),
    [sheet],
  );
  const itemById = useMemo(() => {
    const map = new Map<string, ScoreItem>();
    for (const item of sheet?.items ?? []) map.set(item.student_id, item);
    return map;
  }, [sheet]);

  const submission = useMemo(
    () =>
      submissions.find((item) => item.term_id === assessment?.term_id) ?? null,
    [assessment?.term_id, submissions],
  );

  const termWindows = useMemo(() => {
    if (!assessment) return [];
    return windows.filter(
      (window) =>
        window.term_id === assessment.term_id &&
        (window.section_id === assessment.section_id ||
          (window.section_id === null &&
            window.level_id === assessment.level_id)),
    );
  }, [assessment, windows]);

  let readOnlyReason: string | null = null;
  if (!canEnter) readOnlyReason = "assessment.marks.readonly.permission";
  else if (sheet && !sheet.editable)
    readOnlyReason = "assessment.marks.readonly.archived";
  else if (submission !== null && submission.status !== "draft") {
    readOnlyReason = `assessment.marks.readonly.${submission.status}`;
  } else if (
    termWindows.length > 0 &&
    !termWindows.some((window) => window.state === "open")
  ) {
    readOnlyReason = "assessment.marks.readonly.window";
  }
  const readOnly = readOnlyReason !== null;
  const conflicts = pendingMarks.filter((entry) =>
    conflictKeys.includes(markKey(entry.assessment_id, entry.student_id)),
  );

  const refreshSheet = useCallback(
    async (keep: Set<string>) => {
      if (!profile || !assessmentId) return;
      try {
        const fresh = await getScoreSheet(profile.instanceId, assessmentId);
        setSheet(fresh);
        const previous = draftsRef.current;
        const next: Record<string, MarkDraft> = {};
        for (const item of fresh.items) {
          const kept = previous[item.student_id];
          next[item.student_id] =
            keep.has(item.student_id) && kept ? kept : draftFrom(item);
        }
        setDrafts(next);
      } catch {
        // Keep the current sheet; the outbox still holds the unsynced marks.
      }
    },
    [assessmentId, profile?.instanceId],
  );

  const applyFlush = useCallback(
    async (sent: number, conflicting: PendingMark[]) => {
      const entries = await refreshOutbox();
      const keep = new Set<string>([
        ...entries.map((entry) => entry.student_id),
        ...Object.entries(dirtyRef.current)
          .filter(([, value]) => value)
          .map(([key]) => key),
      ]);
      setConflictKeys(
        conflicting.map((entry) =>
          markKey(entry.assessment_id, entry.student_id),
        ),
      );
      setSync(syncedState(new Set(entries.map((entry) => entry.student_id))));
      await refreshSheet(keep);
      if (conflicting.length > 0)
        setMessage(t("assessment.mobile.conflict_hint"));
      else if (sent > 0) setMessage(t("assessment.mobile.synced"));
      else if (entries.length > 0)
        setMessage(t("assessment.mobile.sync_failed"));
    },
    [refreshOutbox, refreshSheet, t],
  );

  const syncAll = async () => {
    if (!profile) return;
    setSyncing(true);
    setMessage(null);
    try {
      const result = await flushOutbox(profile.instanceId);
      await applyFlush(result.sent, result.conflicts);
    } catch (caught) {
      setMessage(
        t(assessmentErrorKey(caught, "assessment.mobile.sync_failed")),
      );
    } finally {
      setSyncing(false);
    }
  };

  const saveRow = async (studentId: string, override?: MarkDraft) => {
    if (!profile || !assessment || !sheet || readOnly) return;
    const draft = override ?? draftsRef.current[studentId];
    if (!draft) return;
    const item = itemById.get(studentId);
    const queued = pendingRef.current.some(
      (entry) => entry.student_id === studentId,
    );
    if (!isChanged(draft, item) && !queued) return;

    const value = requestValue(draft);
    if (
      value.status === "present" &&
      value.raw_score !== null &&
      isOverMax(value.raw_score, sheet.out_of, sheet.allow_bonus)
    ) {
      setSync((current) => ({ ...current, [studentId]: "error" }));
      setMessage(t("assessment.mobile.over_max", { outOf: sheet.out_of }));
      return;
    }

    setSync((current) => ({ ...current, [studentId]: "saving" }));
    try {
      const result = await saveOrQueue(profile.instanceId, assessment.id, {
        student_id: studentId,
        raw_score: value.raw_score,
        status: value.status,
        row_version: item?.row_version ?? null,
      });
      if (result.sheet) {
        if (queued) {
          await discardMarks(profile.instanceId, [
            { assessment_id: assessment.id, student_id: studentId },
          ]);
          await refreshOutbox();
        }
        setSheet(result.sheet);
        const saved = result.sheet.items.find(
          (entry) => entry.student_id === studentId,
        );
        setDrafts((current) => ({
          ...current,
          [studentId]: saved
            ? draftFrom(saved)
            : { raw: "", status: "present" },
        }));
        setDirty((current) => ({ ...current, [studentId]: false }));
        setSync((current) => ({ ...current, [studentId]: "saved" }));
        setMessage(t("assessment.mobile.saved"));
        setOffline(false);
      } else if (result.conflict) {
        const entries = await refreshOutbox();
        setConflictKeys([markKey(assessment.id, studentId)]);
        setSync((current) => ({ ...current, [studentId]: "conflict" }));
        setMessage(t("assessment.mobile.conflict_hint"));
        if (entries.length > 0) {
          await refreshSheet(new Set(entries.map((entry) => entry.student_id)));
        }
      } else {
        await refreshOutbox();
        setSync((current) => ({ ...current, [studentId]: "pending" }));
        setOffline(true);
        setMessage(t("assessment.mobile.offline"));
      }
    } catch (caught) {
      setSync((current) => ({ ...current, [studentId]: "error" }));
      setMessage(
        t(assessmentErrorKey(caught, "assessment.mobile.save_failed")),
      );
    }
  };

  const editRow = (studentId: string, text: string) => {
    const parsed = parseMarkInput(text);
    if (parsed === null) return;
    setDrafts((current) => ({ ...current, [studentId]: parsed }));
    setDirty((current) => ({ ...current, [studentId]: true }));
    setSync((current) => ({ ...current, [studentId]: "pending" }));
  };

  const setStatus = (studentId: string, status: ScoreStatus) => {
    if (readOnly) return;
    const current = draftsRef.current[studentId] ?? {
      raw: "",
      status: "present" as ScoreStatus,
    };
    const draft: MarkDraft =
      status === "present"
        ? { raw: current.status === "present" ? current.raw : "", status }
        : { raw: "", status };
    setDrafts((values) => ({ ...values, [studentId]: draft }));
    setDirty((values) => ({ ...values, [studentId]: true }));
    void saveRow(studentId, draft);
  };

  const focusNext = (index: number) => {
    const target = rows[nextRowIndex(rows.length, index)];
    if (!target) return;
    inputs.current[target.student_id]?.focus();
  };

  const resolveConflict = async (
    entry: PendingMark,
    choice: "mine" | "server",
  ) => {
    if (!profile || !assessment) return;
    const key = markKey(entry.assessment_id, entry.student_id);
    setMessage(null);
    try {
      if (choice === "server") {
        await discardMarks(profile.instanceId, [entry]);
        const fresh = await getScoreSheet(profile.instanceId, assessment.id);
        const item = fresh.items.find(
          (row) => row.student_id === entry.student_id,
        );
        setSheet(fresh);
        setDrafts((current) => ({
          ...current,
          [entry.student_id]: item
            ? draftFrom(item)
            : { raw: "", status: "present" },
        }));
        setDirty((current) => ({ ...current, [entry.student_id]: false }));
        setSync((current) => {
          const next = { ...current };
          delete next[entry.student_id];
          return next;
        });
      } else {
        const fresh = await getScoreSheet(profile.instanceId, assessment.id);
        const item = fresh.items.find(
          (row) => row.student_id === entry.student_id,
        );
        await queueMarks(profile.instanceId, entry.assessment_id, [
          {
            student_id: entry.student_id,
            raw_score: entry.raw_score,
            status: entry.status,
            row_version: item?.row_version ?? null,
          },
        ]);
        setSheet(fresh);
        const result = await flushOutbox(profile.instanceId);
        await applyFlush(result.sent, result.conflicts);
      }
      setConflictKeys((keys) => keys.filter((value) => value !== key));
      setMessage(t("assessment.mobile.conflict_resolved"));
    } catch (caught) {
      setMessage(
        t(assessmentErrorKey(caught, "assessment.mobile.save_failed")),
      );
    }
  };

  if (!canEnter && !hasPermission(user?.permissions, "assessment.view")) {
    return (
      <Screen colors={colors}>
        <PageHeader colors={colors} title={t("assessment.mobile.title")} />
        <ErrorState
          colors={colors}
          title={t("assessment.mobile.no_permission")}
          description={t("assessment.intro")}
        />
      </Screen>
    );
  }

  return (
    <Screen colors={colors} testID="mark-entry-screen">
      <ScrollView contentContainerStyle={styles.content}>
        <PageHeader
          colors={colors}
          title={assessment?.title ?? t("assessment.mobile.title")}
          subtitle={
            assessment
              ? `${assessment.level_name} ${assessment.section_code} · ${
                  assessment.subject_name
                } · ${assessment.assessment_date}`
              : undefined
          }
          actions={
            pendingMarks.length > 0 ? (
              <Button
                colors={colors}
                secondary
                label={
                  syncing
                    ? t("assessment.mobile.syncing")
                    : t("assessment.mobile.sync")
                }
                busy={syncing}
                onPress={() => void syncAll()}
              />
            ) : undefined
          }
        />

        {assessment && sheet ? (
          <>
            <View style={styles.headerRow}>
              <Muted colors={colors}>
                {t("assessment.mobile.out_of", { outOf: sheet.out_of })}
              </Muted>
              {pendingMarks.length > 0 ? (
                <Muted colors={colors}>
                  {t("assessment.mobile.pending", {
                    count: pendingMarks.length,
                  })}
                </Muted>
              ) : null}
            </View>

            {offline ? (
              <Muted colors={colors}>
                {t("assessment.mobile.offline_mode")}
              </Muted>
            ) : null}
            {message ? (
              <Muted colors={colors}>
                <Text testID="mark-message">{message}</Text>
              </Muted>
            ) : null}
            {readOnlyReason ? (
              <Muted colors={colors}>
                <Text testID="mark-readonly">{t(readOnlyReason)}</Text>
              </Muted>
            ) : null}

            <Card colors={colors} style={styles.stats}>
              <SectionTitle colors={colors}>
                {t("assessment.mobile.progress")}
              </SectionTitle>
              <Muted colors={colors}>
                {t("assessment.mobile.stats", {
                  entered: sheet.stats.entered,
                  total: sheet.stats.total,
                  average: sheet.stats.average_converted ?? "—",
                  highest: sheet.stats.highest_converted ?? "—",
                  lowest: sheet.stats.lowest_converted ?? "—",
                })}
              </Muted>
            </Card>

            <Segmented
              colors={colors}
              items={[
                {
                  key: "card",
                  label: t("assessment.mobile.mode.card"),
                  active: mode === "card",
                  testID: "mark-mode-card",
                  onPress: () => setMode("card"),
                },
                {
                  key: "list",
                  label: t("assessment.mobile.mode.list"),
                  active: mode === "list",
                  testID: "mark-mode-list",
                  onPress: () => setMode("list"),
                },
              ]}
            />

            {conflicts.length > 0 ? (
              <Card colors={colors} style={styles.conflicts}>
                <SectionTitle colors={colors}>
                  {t("assessment.mobile.conflict_title")}
                </SectionTitle>
                <Muted colors={colors}>
                  {t("assessment.mobile.conflict_hint")}
                </Muted>
                {conflicts.map((entry) => {
                  const item = itemById.get(entry.student_id);
                  return (
                    <View
                      key={markKey(entry.assessment_id, entry.student_id)}
                      style={styles.conflictRow}
                      testID={`mark-conflict-${entry.student_id}`}
                    >
                      <Text
                        style={[
                          styles.conflictName,
                          { color: colors.foreground },
                        ]}
                      >
                        {item?.student_name ?? entry.student_id}
                      </Text>
                      <Muted colors={colors}>
                        {entry.status === "present"
                          ? (entry.raw_score ?? "—")
                          : t(`assessment.marks.status.${entry.status}`)}
                      </Muted>
                      <View style={styles.conflictActions}>
                        <Button
                          colors={colors}
                          secondary
                          label={t("assessment.mobile.keep_mine")}
                          onPress={() => void resolveConflict(entry, "mine")}
                        />
                        <Button
                          colors={colors}
                          secondary
                          label={t("assessment.mobile.use_server")}
                          onPress={() => void resolveConflict(entry, "server")}
                        />
                      </View>
                    </View>
                  );
                })}
              </Card>
            ) : null}

            {rows.length === 0 ? (
              <EmptyState
                colors={colors}
                title={t("assessment.mobile.no_students")}
                description={t("assessment.mobile.empty_hint")}
              />
            ) : mode === "card" ? (
              rows.map((item, index) => (
                <Card
                  key={item.student_id}
                  colors={colors}
                  style={styles.cardRow}
                >
                  <MarkRow
                    colors={colors}
                    t={t}
                    item={item}
                    draft={
                      drafts[item.student_id] ?? {
                        raw: item.raw_score ?? "",
                        status: item.status,
                      }
                    }
                    converted={displayConverted(
                      drafts[item.student_id] ?? { raw: "", status: "present" },
                      sheet.out_of,
                      sheet.component_max_points,
                    )}
                    overMax={
                      drafts[item.student_id]?.status === "present" &&
                      isOverMax(
                        drafts[item.student_id]?.raw ?? "",
                        sheet.out_of,
                        sheet.allow_bonus,
                      )
                    }
                    state={sync[item.student_id]}
                    readOnly={readOnly}
                    compact={false}
                    inputRef={(node) => {
                      inputs.current[item.student_id] = node;
                    }}
                    onChangeText={(text) => editRow(item.student_id, text)}
                    onBlur={() => void saveRow(item.student_id)}
                    onSubmit={() => {
                      void saveRow(item.student_id);
                      focusNext(index);
                    }}
                    onStatus={(status) => setStatus(item.student_id, status)}
                  />
                </Card>
              ))
            ) : (
              <Card colors={colors} style={styles.listCard}>
                {rows.map((item, index) => (
                  <View key={item.student_id}>
                    {index > 0 ? <Divider colors={colors} /> : null}
                    <MarkRow
                      colors={colors}
                      t={t}
                      item={item}
                      draft={
                        drafts[item.student_id] ?? {
                          raw: item.raw_score ?? "",
                          status: item.status,
                        }
                      }
                      converted={displayConverted(
                        drafts[item.student_id] ?? {
                          raw: "",
                          status: "present",
                        },
                        sheet.out_of,
                        sheet.component_max_points,
                      )}
                      overMax={
                        drafts[item.student_id]?.status === "present" &&
                        isOverMax(
                          drafts[item.student_id]?.raw ?? "",
                          sheet.out_of,
                          sheet.allow_bonus,
                        )
                      }
                      state={sync[item.student_id]}
                      readOnly={readOnly}
                      compact
                      inputRef={(node) => {
                        inputs.current[item.student_id] = node;
                      }}
                      onChangeText={(text) => editRow(item.student_id, text)}
                      onBlur={() => void saveRow(item.student_id)}
                      onSubmit={() => {
                        void saveRow(item.student_id);
                        focusNext(index);
                      }}
                      onStatus={(status) => setStatus(item.student_id, status)}
                    />
                  </View>
                ))}
              </Card>
            )}
          </>
        ) : loading ? (
          <View style={styles.state}>
            <ActivityIndicator color={colors.primary} />
            <Muted colors={colors}>{t("assessment.mobile.loading")}</Muted>
          </View>
        ) : errorKey ? (
          <ErrorState
            colors={colors}
            title={t("assessment.mobile.load_error")}
            description={t(errorKey)}
            action={
              <Button
                colors={colors}
                secondary
                label={t("common.retry")}
                onPress={() => void load()}
              />
            }
          />
        ) : (
          <EmptyState
            colors={colors}
            title={t("assessment.mobile.not_found")}
          />
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, gap: 12, paddingBottom: 32 },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  stats: { gap: 6 },
  cardRow: { padding: 12 },
  listCard: { padding: 0 },
  row: { gap: 10 },
  rowCard: { padding: 0 },
  rowCompact: { padding: 12 },
  rowHeader: { flexDirection: "row", alignItems: "center", gap: 8 },
  nameBlock: { flex: 1, gap: 2 },
  studentName: { fontSize: 16, fontWeight: "600" },
  inputRow: { flexDirection: "row", alignItems: "flex-end", gap: 12 },
  inputBlock: { flex: 1 },
  convertedBlock: { alignItems: "flex-end", gap: 4, minWidth: 72 },
  convertedLabel: { fontSize: 12 },
  convertedValue: { fontSize: 18, fontWeight: "600" },
  overMax: { fontSize: 12 },
  conflicts: { gap: 10 },
  conflictRow: { gap: 6 },
  conflictName: { fontSize: 15, fontWeight: "600" },
  conflictActions: { flexDirection: "row", gap: 8 },
  state: { alignItems: "center", gap: 8, paddingVertical: 24 },
});
