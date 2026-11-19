import { useRouter } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, View } from "react-native";

import { listAssessments } from "../../../src/assessment/api";
import PortalResultsScreen from "../../../src/assessment/PortalResultsScreen";
import {
  assessmentErrorKey,
  hasPermission,
} from "../../../src/assessment/errors";
import { flushOutbox, loadOutbox } from "../../../src/assessment/outbox";
import type { AssessmentSummary } from "../../../src/assessment/types";
import { useApp } from "../../../src/context/AppContext";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import { listYears } from "../../../src/students/api";
import { useSchoolThemeContext } from "../../../src/theme/SchoolThemeContext";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  ListRow,
  Muted,
  PageHeader,
  Screen,
  SelectField,
  type SelectOption,
} from "../../../src/ui";

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

export default function AssessmentScreen() {
  const { user } = useApp();
  const portal = (user?.roles ?? []).some(
    (role) => role === "parent" || role === "student",
  );
  return portal ? <PortalResultsScreen /> : <AssessmentListScreen />;
}

function AssessmentListScreen() {
  const router = useRouter();
  const { profile, user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canView = hasPermission(user?.permissions, "assessment.view");

  const [years, setYears] = useState<SelectOption[]>([]);
  const [yearId, setYearId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [termId, setTermId] = useState("");
  const [items, setItems] = useState<AssessmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!profile || !yearId || !canView) return;
    setLoading(true);
    setErrorKey(null);
    try {
      const data = await listAssessments(profile.instanceId, yearId);
      setItems(data.items.filter((item) => item.year_id === yearId));
    } catch (caught) {
      setErrorKey(assessmentErrorKey(caught, "assessment.mobile.load_error"));
    } finally {
      setLoading(false);
    }
  }, [canView, profile?.instanceId, yearId]);

  useEffect(() => {
    if (!profile || !canView) return;
    let cancelled = false;
    void listYears(profile.instanceId)
      .then((list) => {
        if (cancelled) return;
        setYears(
          list.items.map((year) => ({ value: year.id, label: year.name })),
        );
        setYearId(
          (current) =>
            current || list.current_year_id || list.items[0]?.id || "",
        );
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [canView, profile?.instanceId]);

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
    if (items.length === 0) return;
    const available = items.filter((item) => item.year_id === yearId);
    if (available.length === 0) return;
    if (!available.some((item) => item.section_id === sectionId)) {
      setSectionId(available[0]!.section_id);
      return;
    }
    const sectionItems = available.filter(
      (item) => item.section_id === sectionId,
    );
    if (!sectionItems.some((item) => item.subject_id === subjectId)) {
      setSubjectId(sectionItems[0]!.subject_id);
      return;
    }
    const subjectItems = sectionItems.filter(
      (item) => item.subject_id === subjectId,
    );
    if (!subjectItems.some((item) => item.term_id === termId)) {
      setTermId(subjectItems[0]!.term_id ?? "");
    }
  }, [items, yearId, sectionId, subjectId, termId]);

  const scoped = useMemo(
    () => items.filter((item) => item.year_id === yearId),
    [items, yearId],
  );
  const sectionOptions = useMemo(
    () =>
      uniqueBy(scoped, (item) => item.section_id).map((item) => ({
        value: item.section_id,
        label: `${item.level_name} ${item.section_code}`,
      })),
    [scoped],
  );
  const subjectOptions = useMemo(
    () =>
      uniqueBy(
        scoped.filter((item) => item.section_id === sectionId),
        (item) => item.subject_id,
      ).map((item) => ({ value: item.subject_id, label: item.subject_name })),
    [scoped, sectionId],
  );
  const termOptions = useMemo(
    () =>
      uniqueBy(
        scoped.filter(
          (item) =>
            item.section_id === sectionId && item.subject_id === subjectId,
        ),
        (item) => item.term_id,
      ).map((item) => ({ value: item.term_id, label: item.term_name })),
    [scoped, sectionId, subjectId],
  );
  const rows = useMemo(
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
            left.title.localeCompare(right.title),
        ),
    [scoped, sectionId, subjectId, termId],
  );

  const sync = useCallback(async () => {
    if (!profile) return;
    setSyncing(true);
    setMessage(null);
    try {
      const result = await flushOutbox(profile.instanceId);
      setPending(result.pending);
      if (result.conflicts.length > 0)
        setMessage(t("assessment.mobile.conflict_hint"));
      else if (result.sent > 0) setMessage(t("assessment.mobile.synced"));
      else if (result.pending > 0)
        setMessage(t("assessment.mobile.sync_failed"));
    } catch {
      setMessage(t("assessment.mobile.sync_failed"));
    } finally {
      setSyncing(false);
    }
  }, [profile?.instanceId, t]);

  if (!canView) {
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
    <ScrollView
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={styles.content}
      testID="assessment-list-screen"
    >
      <PageHeader
        colors={colors}
        title={t("assessment.mobile.title")}
        subtitle={t("assessment.mobile.intro")}
        actions={
          pending > 0 ? (
            <Button
              colors={colors}
              secondary
              label={
                syncing
                  ? t("assessment.mobile.syncing")
                  : t("assessment.mobile.sync")
              }
              busy={syncing}
              onPress={() => void sync()}
            />
          ) : undefined
        }
      />

      {pending > 0 ? (
        <Muted colors={colors}>
          {t("assessment.mobile.pending", { count: pending })}
        </Muted>
      ) : null}
      {message ? <Muted colors={colors}>{message}</Muted> : null}

      <Card colors={colors} style={styles.filters}>
        <SelectField
          colors={colors}
          label={t("assessment.mobile.year")}
          value={yearId}
          options={years}
          onChange={(value) => {
            setYearId(value);
            setSectionId("");
            setSubjectId("");
            setTermId("");
          }}
          testID="assessment-year"
        />
        <SelectField
          colors={colors}
          label={t("assessment.mobile.section")}
          value={sectionId}
          options={sectionOptions}
          onChange={(value) => {
            setSectionId(value);
            setSubjectId("");
            setTermId("");
          }}
          testID="assessment-section"
        />
        <SelectField
          colors={colors}
          label={t("assessment.mobile.subject")}
          value={subjectId}
          options={subjectOptions}
          onChange={(value) => {
            setSubjectId(value);
            setTermId("");
          }}
          testID="assessment-subject"
        />
        <SelectField
          colors={colors}
          label={t("assessment.mobile.term")}
          value={termId}
          options={termOptions}
          onChange={setTermId}
          testID="assessment-term"
        />
      </Card>

      {loading ? (
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
      ) : rows.length === 0 ? (
        <EmptyState
          colors={colors}
          title={t("assessment.mobile.empty")}
          description={t("assessment.mobile.empty_hint")}
        />
      ) : (
        <Card colors={colors} style={styles.list}>
          {rows.map((item) => (
            <ListRow
              key={item.id}
              colors={colors}
              title={item.title}
              subtitle={`${item.assessment_date} · ${t(
                "assessment.mobile.out_of",
                {
                  outOf: item.out_of,
                },
              )}`}
              right={
                <Badge
                  colors={colors}
                  tone={item.entered > 0 ? "success" : "neutral"}
                >
                  {t("assessment.mobile.entered_count", {
                    count: item.entered,
                  })}
                </Badge>
              }
              testID={`assessment-row-${item.id}`}
              onPress={() =>
                router.push({
                  pathname: "/(app)/assessment/[assessmentId]",
                  params: { assessmentId: item.id },
                })
              }
            />
          ))}
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, gap: 12, paddingBottom: 32 },
  filters: { gap: 12 },
  list: { padding: 0, gap: 0 },
  state: { alignItems: "center", gap: 8, paddingVertical: 24 },
});
