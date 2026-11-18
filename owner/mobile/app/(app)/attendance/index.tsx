import { useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useApp } from "../../../src/context/AppContext";
import {
  createSession,
  listSessions,
} from "../../../src/attendance/api";
import { attendanceErrorKey, hasPermission, statusTone } from "../../../src/attendance/errors";
import { flushOutbox, loadOutbox } from "../../../src/attendance/outbox";
import { todayIso, type SessionSummary } from "../../../src/attendance/types";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import { listLevels, listSections, listYears } from "../../../src/students/api";
import type {
  AcademicLevel,
  AcademicSection,
  AcademicYear,
} from "../../../src/students/types";
import { useSchoolThemeContext } from "../../../src/theme/SchoolThemeContext";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  ListRow,
  Muted,
  PageHeader,
  Screen,
  SelectField,
  SectionTitle,
  type SelectOption,
} from "../../../src/ui";

export default function AttendanceScreen() {
  const router = useRouter();
  const { profile, user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canView = hasPermission(user?.permissions, "attendance.view");
  const canRecord = hasPermission(user?.permissions, "attendance.record");

  const [date, setDate] = useState(todayIso());
  const [items, setItems] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const [years, setYears] = useState<AcademicYear[]>([]);
  const [levels, setLevels] = useState<AcademicLevel[]>([]);
  const [sections, setSections] = useState<AcademicSection[]>([]);
  const [yearId, setYearId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [period, setPeriod] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!profile || !canView) return;
    setLoading(true);
    setErrorKey(null);
    try {
      const data = await listSessions(profile.instanceId, { date });
      setItems(data.items);
    } catch (caught) {
      setErrorKey(attendanceErrorKey(caught, "attendance.session.load_error"));
    } finally {
      setLoading(false);
    }
  }, [canView, date, profile?.instanceId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!profile) return;
    void loadOutbox(profile.instanceId)
      .then((entries) => setPending(entries.length))
      .catch(() => setPending(0));
  }, [profile?.instanceId]);

  useEffect(() => {
    if (!profile) return;
    let cancelled = false;
    void Promise.all([listYears(profile.instanceId), listLevels(profile.instanceId)])
      .then(([yearList, levelList]) => {
        if (cancelled) return;
        setYears(yearList.items);
        setLevels(levelList.items);
        setYearId((current) => current || yearList.current_year_id || yearList.items[0]?.id || "");
        setLevelId((current) => current || levelList.items[0]?.id || "");
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [profile?.instanceId]);

  useEffect(() => {
    if (!profile || !yearId || !levelId) return;
    let cancelled = false;
    void listSections(profile.instanceId, yearId, levelId)
      .then((list) => {
        if (cancelled) return;
        setSections(list.items);
        setSectionId((current) =>
          list.items.some((section) => section.id === current)
            ? current
            : list.items[0]?.id ?? "",
        );
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [profile?.instanceId, yearId, levelId]);

  async function sync(): Promise<void> {
    if (!profile) return;
    setSyncing(true);
    setSyncMessage(null);
    try {
      const result = await flushOutbox(profile.instanceId);
      setPending(result.pending);
      if (result.sent > 0) {
        setSyncMessage(t("attendance.record.synced"));
        await load();
      } else if (result.pending > 0) {
        setSyncMessage(t("attendance.record.sync_failed"));
      }
    } catch {
      setSyncMessage(t("attendance.record.sync_failed"));
    } finally {
      setSyncing(false);
    }
  }

  async function open(): Promise<void> {
    if (!profile || !yearId || !sectionId) return;
    setCreating(true);
    setCreateError(null);
    try {
      await createSession(profile.instanceId, {
        year_id: yearId,
        section_id: sectionId,
        date,
        period: period.trim() ? Number(period) : null,
      });
      setPeriod("");
      await load();
    } catch (caught) {
      setCreateError(attendanceErrorKey(caught, "attendance.session.create_failed"));
    } finally {
      setCreating(false);
    }
  }

  function openSession(session: SessionSummary): void {
    router.push({
      pathname: "/(app)/attendance/[sessionId]",
      params: { sessionId: session.id },
    });
  }

  const yearOptions: SelectOption[] = years.map((year) => ({
    value: year.id,
    label: year.name,
  }));
  const levelOptions: SelectOption[] = levels.map((level) => ({
    value: level.id,
    label: level.name,
  }));
  const sectionOptions: SelectOption[] = sections.map((section) => ({
    value: section.id,
    label: section.name ?? section.code,
  }));

  return (
    <Screen colors={colors} testID="attendance-screen">
      <PageHeader
        colors={colors}
        title={t("attendance.title")}
        subtitle={t("attendance.intro")}
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

      {!canView ? (
        <ErrorState colors={colors} title={t("attendance.permission_denied")} />
      ) : (
        <>
          {pending > 0 ? (
            <Muted colors={colors}>{t("attendance.record.pending", { count: pending })}</Muted>
          ) : null}
          {syncMessage ? <Muted colors={colors}>{syncMessage}</Muted> : null}

          <Field
            colors={colors}
            label={t("attendance.session.date")}
            value={date}
            onChangeText={setDate}
            hint={t("attendance.session.date_hint")}
            autoCapitalize="none"
            testID="attendance-date"
          />

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
          ) : items.length === 0 ? (
            <EmptyState
              colors={colors}
              title={t("attendance.session.empty")}
              description={t("attendance.session.empty_hint")}
            />
          ) : (
            <Card colors={colors} style={styles.list}>
              {items.map((session) => (
                <ListRow
                  key={session.id}
                  colors={colors}
                  testID={`attendance-row-${session.id}`}
                  title={`${session.level_name} · ${session.section_name ?? session.section_code}`}
                  subtitle={[
                    session.date,
                    t(`attendance.mode.${session.mode}`),
                    session.period ? `${t("attendance.session.period")} ${session.period}` : "",
                    t("attendance.count.present", { count: session.counts.present }),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  right={
                    <Badge colors={colors} tone={statusTone(session.status)}>
                      {t(`attendance.status.${session.status}`)}
                    </Badge>
                  }
                  onPress={() => openSession(session)}
                />
              ))}
            </Card>
          )}

          {canRecord ? (
            <Card colors={colors} style={styles.create}>
              <SectionTitle colors={colors}>{t("attendance.session.open_title")}</SectionTitle>
              <Muted colors={colors}>{t("attendance.session.open_hint")}</Muted>
              <SelectField
                colors={colors}
                label={t("attendance.session.year")}
                value={yearId}
                options={yearOptions}
                onChange={(value) => {
                  setYearId(value);
                  setSectionId("");
                }}
                testID="attendance-year"
              />
              <SelectField
                colors={colors}
                label={t("attendance.session.level")}
                value={levelId}
                options={levelOptions}
                onChange={(value) => {
                  setLevelId(value);
                  setSectionId("");
                }}
                testID="attendance-level"
              />
              <SelectField
                colors={colors}
                label={t("attendance.session.section")}
                value={sectionId}
                options={sectionOptions}
                onChange={setSectionId}
                placeholder={t("attendance.session.choose_section")}
                testID="attendance-section"
              />
              <Field
                colors={colors}
                label={t("attendance.session.period")}
                value={period}
                onChangeText={setPeriod}
                keyboardType="number-pad"
                testID="attendance-period"
              />
              {createError ? (
                <Muted colors={colors}>{t(createError)}</Muted>
              ) : null}
              <Button
                colors={colors}
                label={creating ? t("attendance.session.opening") : t("attendance.session.create")}
                busy={creating}
                disabled={!sectionId}
                onPress={() => void open()}
              />
            </Card>
          ) : null}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  state: { alignItems: "center", gap: 8, paddingVertical: 24 },
  list: { paddingVertical: 0, paddingHorizontal: 0 },
  create: { gap: 10 },
});
