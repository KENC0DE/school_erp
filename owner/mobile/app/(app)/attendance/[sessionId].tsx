import { useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { getSession, submitSession } from "../../../src/attendance/api";
import {
  attendanceErrorKey,
  hasPermission,
  statusTone,
} from "../../../src/attendance/errors";
import {
  flushOutbox,
  loadOutbox,
  saveOrQueue,
} from "../../../src/attendance/outbox";
import {
  RECORD_STATUSES,
  changedRecords,
  draftsFrom,
  type RecordDraft,
  type RecordStatus,
  type SessionDetail,
} from "../../../src/attendance/types";
import { useApp } from "../../../src/context/AppContext";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import { useSchoolThemeContext } from "../../../src/theme/SchoolThemeContext";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Field,
  Muted,
  PageHeader,
  Screen,
  Segmented,
  SectionTitle,
} from "../../../src/ui";

export default function AttendanceSessionScreen() {
  const params = useLocalSearchParams<{ sessionId?: string }>();
  const sessionId = typeof params.sessionId === "string" ? params.sessionId : "";
  const { profile, user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canRecord = hasPermission(user?.permissions, "attendance.record");

  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [drafts, setDrafts] = useState<Record<string, RecordDraft>>({});
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    if (!profile || !sessionId) return;
    setLoading(true);
    setErrorKey(null);
    try {
      const data = await getSession(profile.instanceId, sessionId);
      setDetail(data);
      setDrafts(draftsFrom(data));
    } catch (caught) {
      setErrorKey(attendanceErrorKey(caught, "attendance.session.load_error"));
    } finally {
      setLoading(false);
    }
  }, [profile?.instanceId, sessionId]);

  const sync = useCallback(async () => {
    if (!profile) return;
    setSyncing(true);
    try {
      const result = await flushOutbox(profile.instanceId);
      setPending(result.pending);
      if (result.sent > 0) {
        setMessage(t("attendance.record.synced"));
        await load();
      } else if (result.pending > 0) {
        setMessage(t("attendance.record.sync_failed"));
      }
    } catch {
      setMessage(t("attendance.record.sync_failed"));
    } finally {
      setSyncing(false);
    }
  }, [load, profile?.instanceId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!profile) return;
    void loadOutbox(profile.instanceId)
      .then((entries) => setPending(entries.length))
      .catch(() => setPending(0));
  }, [profile?.instanceId]);

  function update(studentId: string, patch: Partial<RecordDraft>): void {
    setDrafts((current) => {
      const base: RecordDraft = current[studentId] ?? {
        status: "present",
        reason: "",
        late_minutes: "",
      };
      return { ...current, [studentId]: { ...base, ...patch } };
    });
  }

  function markAllPresent(): void {
    setDrafts((current) => {
      const next: Record<string, RecordDraft> = {};
      for (const [studentId, draft] of Object.entries(current)) {
        next[studentId] = { ...draft, status: "present", reason: "", late_minutes: "" };
      }
      return next;
    });
  }

  async function save(): Promise<void> {
    if (!profile || !detail) return;
    const items = changedRecords(detail, drafts);
    if (items.length === 0) {
      setMessage(t("attendance.record.no_changes"));
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const result = await saveOrQueue(profile.instanceId, detail.id, items);
      if (result.detail) {
        setDetail(result.detail);
        setDrafts(draftsFrom(result.detail));
        setMessage(t("attendance.record.saved"));
      } else {
        setPending(result.queued);
        setMessage(t("attendance.record.offline"));
      }
    } catch (caught) {
      setMessage(t(attendanceErrorKey(caught, "attendance.record.save_failed")));
    } finally {
      setSaving(false);
    }
  }

  async function submit(): Promise<void> {
    if (!profile || !detail) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const updated = await submitSession(profile.instanceId, detail.id);
      setDetail(updated);
      setDrafts(draftsFrom(updated));
      setMessage(t("attendance.record.saved"));
    } catch (caught) {
      setMessage(t(attendanceErrorKey(caught, "attendance.session.submit_failed")));
    } finally {
      setSubmitting(false);
    }
  }

  const editable = detail?.status === "open" && canRecord;

  return (
    <Screen colors={colors} testID="attendance-session-screen">
      <PageHeader
        colors={colors}
        title={
          detail
            ? `${detail.level_name} · ${detail.section_name ?? detail.section_code}`
            : t("attendance.record.roster")
        }
        subtitle={detail ? `${detail.date} · ${t(`attendance.mode.${detail.mode}`)}` : undefined}
        actions={
          pending > 0 ? (
            <Button
              colors={colors}
              secondary
              label={syncing ? t("attendance.record.syncing") : t("attendance.record.sync")}
              busy={syncing}
              onPress={() => void sync()}
            />
          ) : undefined
        }
      />

      {pending > 0 ? (
        <Muted colors={colors}>{t("attendance.record.pending", { count: pending })}</Muted>
      ) : null}
      {message ? <Muted colors={colors}>{message}</Muted> : null}

      {loading ? (
        <View style={styles.state}>
          <ActivityIndicator color={colors.primary} />
          <Muted colors={colors}>{t("attendance.session.loading")}</Muted>
        </View>
      ) : errorKey ? (
        <ErrorState
          colors={colors}
          title={t("attendance.session.load_error")}
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
      ) : !detail ? (
        <ErrorState colors={colors} title={t("attendance.session.not_found")} />
      ) : (
        <>
          <Card colors={colors} style={styles.summary}>
            <View style={styles.summaryRow}>
              <SectionTitle colors={colors}>{t("attendance.record.roster")}</SectionTitle>
              <Badge colors={colors} tone={statusTone(detail.status)}>
                {t(`attendance.status.${detail.status}`)}
              </Badge>
            </View>
            <Muted colors={colors}>
              {t("attendance.count.total", { count: detail.counts.total })} ·{" "}
              {t("attendance.count.present", { count: detail.counts.present })} ·{" "}
              {t("attendance.count.absent", { count: detail.counts.absent })}
            </Muted>
            <Muted colors={colors}>{t("attendance.record.quick_hint")}</Muted>
            {detail.status !== "open" ? (
              <Muted colors={colors}>{t("attendance.session.closed")}</Muted>
            ) : null}
          </Card>

          {detail.roster.length === 0 ? (
            <ErrorState colors={colors} title={t("attendance.record.empty")} />
          ) : (
            detail.roster.map((entry) => {
              const draft = drafts[entry.student_id] ?? {
                status: "present" as RecordStatus,
                reason: "",
                late_minutes: "",
              };
              return (
                <Card key={entry.student_id} colors={colors} style={styles.student}>
                  <View style={styles.summaryRow}>
                    <View style={styles.nameBlock}>
                      <SectionTitle colors={colors}>{entry.full_name}</SectionTitle>
                      <Muted colors={colors}>
                        {entry.roll_number
                          ? `${t("attendance.record.roll_number")} ${entry.roll_number}`
                          : entry.student_number}
                      </Muted>
                    </View>
                    <Badge colors={colors} tone={statusTone(draft.status)}>
                      {t(`attendance.record.${draft.status}`)}
                    </Badge>
                  </View>

                  <Segmented
                    colors={colors}
                    items={RECORD_STATUSES.map((status) => ({
                      key: status,
                      label: t(`attendance.record.${status}`),
                      active: draft.status === status,
                      testID: `attendance-status-${entry.student_id}-${status}`,
                      onPress: () =>
                        update(entry.student_id, {
                          status,
                          reason: status === "present" ? "" : draft.reason,
                          late_minutes: status === "late" ? draft.late_minutes : "",
                        }),
                    }))}
                  />

                  {draft.status !== "present" ? (
                    <Field
                      colors={colors}
                      label={t("attendance.record.reason")}
                      value={draft.reason}
                      onChangeText={(value) => update(entry.student_id, { reason: value })}
                      testID={`attendance-reason-${entry.student_id}`}
                    />
                  ) : null}

                  {draft.status === "late" ? (
                    <Field
                      colors={colors}
                      label={t("attendance.record.late_minutes")}
                      value={draft.late_minutes}
                      onChangeText={(value) =>
                        update(entry.student_id, { late_minutes: value })
                      }
                      keyboardType="number-pad"
                      testID={`attendance-late-${entry.student_id}`}
                    />
                  ) : null}
                </Card>
              );
            })
          )}

          <View style={styles.actions}>
            {editable ? (
              <>
                <Button
                  colors={colors}
                  label={saving ? t("attendance.record.saving") : t("attendance.record.save")}
                  busy={saving}
                  onPress={() => void save()}
                />
                <Button
                  colors={colors}
                  secondary
                  label={t("attendance.record.mark_all_present")}
                  onPress={markAllPresent}
                />
                <Button
                  colors={colors}
                  secondary
                  label={
                    submitting ? t("attendance.session.submitting") : t("attendance.session.submit")
                  }
                  busy={submitting}
                  onPress={() => void submit()}
                />
              </>
            ) : null}
            {pending > 0 ? (
              <Button
                colors={colors}
                secondary
                label={syncing ? t("attendance.record.syncing") : t("attendance.record.sync")}
                busy={syncing}
                onPress={() => void sync()}
              />
            ) : null}
          </View>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  state: { alignItems: "center", gap: 8, paddingVertical: 24 },
  summary: { gap: 8 },
  summaryRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  nameBlock: { flex: 1, gap: 2 },
  student: { gap: 10 },
  actions: { gap: 10, marginTop: 8, marginBottom: 32 },
});
