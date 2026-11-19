import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, View } from "react-native";

import { useApp } from "../context/AppContext";
import { useSchoolI18n } from "../i18n/SchoolI18nContext";
import { useSchoolThemeContext } from "../theme/SchoolThemeContext";
import { listYears } from "../students/api";
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
} from "../ui";
import { getPortalResults } from "./api";
import { assessmentErrorKey } from "./errors";
import type { PortalChild, PortalResult } from "./types";

function shortDate(value: string): string {
  return value.slice(0, 10);
}

function rankText(rank: number | null, size: number | null): string {
  if (rank === null) return "—";
  return size === null ? String(rank) : `${rank}/${size}`;
}

export default function PortalResultsScreen() {
  const { profile } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const [years, setYears] = useState<SelectOption[]>([]);
  const [yearId, setYearId] = useState("");
  const [children, setChildren] = useState<PortalChild[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);

  useEffect(() => {
    if (!profile) return;
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
  }, [profile?.instanceId]);

  const load = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    setErrorKey(null);
    try {
      const data = await getPortalResults(profile.instanceId, yearId);
      setChildren(data.children);
    } catch (caught) {
      setErrorKey(assessmentErrorKey(caught, "assessment.portal.load_error"));
    } finally {
      setLoading(false);
    }
  }, [profile?.instanceId, yearId]);

  useEffect(() => {
    void load();
  }, [load]);

  function renderResult(result: PortalResult) {
    const value = result.result;
    const title =
      result.kind === "year"
        ? t("assessment.portal.year_result")
        : t("assessment.portal.term_result", {
            term: result.term_name ?? result.year_code,
          });
    return (
      <Card key={result.snapshot_id} colors={colors} style={styles.card}>
        <View testID="portal-result">
          <Muted colors={colors}>{title}</Muted>
          <Muted colors={colors}>
            {result.level_name} {result.section_code} ·{" "}
            {t("assessment.portal.published", {
              date: shortDate(result.published_at),
            })}
          </Muted>
          <View style={[styles.rows, { borderTopColor: colors.border }]}>
            {value.subjects.map((subject) => (
              <ListRow
                key={subject.subject_id}
                colors={colors}
                testID={`portal-subject-${subject.subject_id}`}
                title={subject.subject_name}
                subtitle={`${t("assessment.portal.of", {
                  total: subject.total,
                  out_of: subject.out_of,
                })} · ${subject.percent}%${
                  subject.grade_remark ? ` · ${subject.grade_remark}` : ""
                }`}
                right={
                  <Badge
                    colors={colors}
                    tone={subject.is_pass ? "success" : "danger"}
                  >
                    {subject.grade_label ?? "—"}
                  </Badge>
                }
              />
            ))}
          </View>
          <View style={[styles.summary, { borderTopColor: colors.border }]}>
            <Muted colors={colors}>{t("assessment.portal.overall")}</Muted>
            <Muted colors={colors}>
              {t("assessment.portal.of", {
                total: value.total,
                out_of: value.out_of,
              })}{" "}
              · {value.percent}% · {rankText(value.rank, value.rank_size)}
            </Muted>
            <Badge colors={colors} tone={value.is_pass ? "success" : "danger"}>
              {value.is_pass
                ? t("assessment.portal.pass")
                : t("assessment.portal.fail")}
            </Badge>
          </View>
        </View>
      </Card>
    );
  }

  return (
    <Screen colors={colors}>
      <ScrollView contentContainerStyle={styles.content} testID="portal-screen">
        <PageHeader
          colors={colors}
          title={t("assessment.portal.title")}
          subtitle={t("assessment.portal.intro")}
        />
        <SelectField
          colors={colors}
          label={t("assessment.portal.year")}
          value={yearId}
          options={years}
          onChange={setYearId}
          testID="portal-year"
        />
        {loading ? <ActivityIndicator color={colors.primary} /> : null}
        {errorKey && !loading ? (
          <ErrorState
            colors={colors}
            title={t(errorKey)}
            action={
              <Button
                colors={colors}
                secondary
                label={t("common.retry")}
                onPress={() => void load()}
              />
            }
          />
        ) : null}
        {!loading && !errorKey && children.length === 0 ? (
          <EmptyState
            colors={colors}
            title={t("assessment.portal.empty")}
            description={t("assessment.portal.empty_hint")}
          />
        ) : null}
        {!loading
          ? children.map((child) => (
              <View
                key={child.student_id}
                style={styles.child}
                testID="portal-child"
              >
                <PageHeader
                  colors={colors}
                  title={child.student_name}
                  subtitle={child.student_number}
                />
                {child.results.map(renderResult)}
              </View>
            ))
          : null}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, gap: 16 },
  child: { gap: 12 },
  card: { padding: 12, gap: 6 },
  rows: { marginTop: 8, borderTopWidth: StyleSheet.hairlineWidth },
  summary: {
    marginTop: 8,
    paddingTop: 8,
    gap: 4,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
});
