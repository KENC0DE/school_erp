import { formatDual, parseIsoDate } from "@erp/calendar";
import { formatSantim } from "@erp/money";
import { Redirect } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { translateUi, type UiKey } from "../src/i18n/ui-messages";
import { defaultNativeTheme } from "../src/theme/nativeTheme";
import type { ThemeMode } from "../src/theme/useSchoolTheme";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  ListRow,
  PageHeader,
  SaveBar,
  Screen,
  SectionTitle,
  Segmented,
  Skeleton,
  Toast,
  font,
  radius,
  space,
  text,
  touch,
  type Palette,
} from "../src/ui";

type DesignLocale = "en" | "am";

const ROWS = [
  { id: "1", name: "Abebe Kebede", amharic: "አበበ ከበደ", status: "active" as const, updated: "2026-09-11" },
  { id: "2", name: "Hana Tesfaye", amharic: "ሃና ተስፋዬ", status: "pending" as const, updated: "2026-09-12" },
  { id: "3", name: "Dawit Alemu", amharic: "ዳዊት አለሙ", status: "active" as const, updated: "2026-09-14" },
];

type ListState = "ready" | "loading" | "empty" | "error";
type ReferenceTab = "list" | "form" | "dashboard";

export default function DesignRoute() {
  if (!__DEV__) return <Redirect href="/" />;
  return <DesignPreview />;
}

function DesignPreview() {
  const [locale, setLocale] = useState<DesignLocale>("en");
  const [mode, setMode] = useState<ThemeMode>("light");
  const [tab, setTab] = useState<ReferenceTab>("list");
  const colors = useMemo(() => defaultNativeTheme(mode).colors, [mode]);
  const t = (key: UiKey) => translateUi(locale, key);

  return (
    <SafeAreaView
      edges={["top", "left", "right", "bottom"]}
      style={[styles.root, { backgroundColor: colors.background }]}
    >
      <View style={[styles.bar, { borderBottomColor: colors.border }]}>
        <Text style={[styles.barTitle, { color: colors.foreground }]}>{t("design.title")}</Text>
        <View style={styles.controls}>
          <Toggle
            colors={colors}
            testID="design-locale"
            label={locale === "en" ? "አማርኛ" : "English"}
            onPress={() => setLocale(locale === "en" ? "am" : "en")}
          />
          <Toggle
            colors={colors}
            testID="design-mode"
            label={t(mode === "light" ? "design.dark" : "design.light")}
            onPress={() => setMode(mode === "light" ? "dark" : "light")}
          />
        </View>
      </View>
      <View style={styles.segmentWrap}>
        <Segmented
          colors={colors}
          items={[
            {
              key: "list",
              label: t("design.tab.list"),
              active: tab === "list",
              onPress: () => setTab("list"),
              testID: "design-tab-list",
            },
            {
              key: "form",
              label: t("design.tab.form"),
              active: tab === "form",
              onPress: () => setTab("form"),
              testID: "design-tab-form",
            },
            {
              key: "dashboard",
              label: t("design.tab.dashboard"),
              active: tab === "dashboard",
              onPress: () => setTab("dashboard"),
              testID: "design-tab-dashboard",
            },
          ]}
        />
      </View>
      {tab === "list" ? <ReferenceList colors={colors} t={t} /> : null}
      {tab === "form" ? <ReferenceForm colors={colors} t={t} locale={locale} /> : null}
      {tab === "dashboard" ? <ReferenceDashboard colors={colors} t={t} /> : null}
    </SafeAreaView>
  );
}

type Translate = (key: UiKey) => string;

function Toggle({
  colors,
  label,
  onPress,
  testID,
}: {
  colors: Palette;
  label: string;
  onPress: () => void;
  testID?: string;
}) {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [
        styles.toggle,
        { backgroundColor: pressed ? colors.muted : colors.secondary },
      ]}
    >
      <Text style={[styles.toggleLabel, { color: colors.foreground }]}>{label}</Text>
    </Pressable>
  );
}

function ReferenceList({ colors, t }: { colors: Palette; t: Translate }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "pending">("all");
  const [state, setState] = useState<ListState>("ready");

  const rows = ROWS.filter((row) => {
    const matchesStatus = status === "all" || row.status === status;
    const needle = search.trim().toLowerCase();
    const matchesSearch =
      needle === "" || row.name.toLowerCase().includes(needle) || row.amharic.includes(search.trim());
    return matchesStatus && matchesSearch;
  });

  return (
    <Screen colors={colors} testID="design-list">
      <PageHeader colors={colors} title={t("design.list.title")} subtitle={t("design.list.subtitle")} />
      <Card colors={colors}>
        <Field
          colors={colors}
          label={t("design.filter.search")}
          placeholder={t("design.filter.search.hint")}
          value={search}
          onChangeText={setSearch}
        />
        <View style={styles.gapXs}>
          <Text style={[styles.fieldLabel, { color: colors.foreground }]}>{t("design.filter.status")}</Text>
          <Segmented
            colors={colors}
            items={[
              { key: "all", label: t("design.filter.all"), active: status === "all", onPress: () => setStatus("all") },
              { key: "active", label: t("design.status.active"), active: status === "active", onPress: () => setStatus("active") },
              { key: "pending", label: t("design.status.pending"), active: status === "pending", onPress: () => setStatus("pending") },
            ]}
          />
        </View>
        <Segmented
          colors={colors}
          items={[
            {
              key: "ready",
              label: t("design.state.ready"),
              active: state === "ready",
              onPress: () => setState("ready"),
              testID: "design-state-ready",
            },
            {
              key: "loading",
              label: t("design.state.loading"),
              active: state === "loading",
              onPress: () => setState("loading"),
              testID: "design-state-loading",
            },
            {
              key: "empty",
              label: t("design.state.empty"),
              active: state === "empty",
              onPress: () => setState("empty"),
              testID: "design-state-empty",
            },
            {
              key: "error",
              label: t("design.state.error"),
              active: state === "error",
              onPress: () => setState("error"),
              testID: "design-state-error",
            },
          ]}
        />
      </Card>
      <Button colors={colors} label={t("design.add")} onPress={() => undefined} />
      {state === "error" ? (
        <Card colors={colors}>
          <ErrorState
            colors={colors}
            title={t("design.error.title")}
            description={t("design.error.body")}
            requestId="demo-request-1"
            requestIdLabel={t("design.requestId")}
            action={<Button colors={colors} secondary label={t("design.retry")} onPress={() => setState("ready")} />}
          />
        </Card>
      ) : state === "empty" ? (
        <Card colors={colors}>
          <EmptyState
            colors={colors}
            title={t("design.empty.title")}
            description={t("design.empty.body")}
            action={<Button colors={colors} label={t("design.empty.action")} onPress={() => setState("ready")} />}
          />
        </Card>
      ) : (
        <Card colors={colors} style={styles.listCard}>
          {state === "loading" ? (
            <View style={styles.gapSm}>
              <Skeleton colors={colors} height={20} width="60%" />
              <Skeleton colors={colors} height={56} />
              <Skeleton colors={colors} height={56} />
              <Skeleton colors={colors} height={56} />
            </View>
          ) : rows.length === 0 ? (
            <EmptyState colors={colors} title={t("design.empty.title")} description={t("design.empty.body")} />
          ) : (
            rows.map((row) => (
              <ListRow
                key={row.id}
                colors={colors}
                title={row.name}
                subtitle={`${row.amharic} · ${row.updated}`}
                right={
                  <Badge colors={colors} tone={row.status === "active" ? "success" : "warning"}>
                    {t(row.status === "active" ? "design.status.active" : "design.status.pending")}
                  </Badge>
                }
              />
            ))
          )}
        </Card>
      )}
    </Screen>
  );
}

function ReferenceForm({
  colors,
  t,
  locale,
}: {
  colors: Palette;
  t: Translate;
  locale: DesignLocale;
}) {
  const [saved, setSaved] = useState(false);
  return (
    <View style={styles.formRoot}>
      <Screen colors={colors} testID="design-form">
        <PageHeader colors={colors} title={t("design.form.title")} subtitle={t("design.form.subtitle")} />
        {saved ? (
          <Toast
            colors={colors}
            tone="success"
            message={t("design.form.saved")}
            dismissLabel={t("design.close")}
            onDismiss={() => setSaved(false)}
          />
        ) : null}
        <Card colors={colors}>
          <Field colors={colors} label={t("design.form.first")} defaultValue="Abebe" required />
          <Field colors={colors} label={t("design.form.middle")} defaultValue="Kebede" />
          <Field
            colors={colors}
            label={t("design.form.amharic")}
            hint={t("design.form.amharic.hint")}
            defaultValue="አበበ ከበደ"
          />
        </Card>
        <Card colors={colors}>
          <SectionTitle colors={colors}>{t("design.form.status")}</SectionTitle>
          <Badge colors={colors} tone="success">
            {t("design.status.active")}
          </Badge>
          <Field
            colors={colors}
            label={t("design.form.date")}
            defaultValue="2026-09-11"
            hint={formatDual(parseIsoDate("2026-09-11") ?? new Date(), "both", locale)}
          />
          <Field
            colors={colors}
            label={t("design.form.notes")}
            placeholder={t("design.form.notes.hint")}
            multiline
          />
        </Card>
      </Screen>
      <SaveBar colors={colors}>
        <View style={styles.action}>
          <Button colors={colors} secondary label={t("design.form.cancel")} onPress={() => undefined} />
        </View>
        <View style={styles.action}>
          <Button colors={colors} label={t("design.form.save")} onPress={() => setSaved(true)} />
        </View>
      </SaveBar>
    </View>
  );
}

function ReferenceDashboard({ colors, t }: { colors: Palette; t: Translate }) {
  const stats = [
    { key: "students", value: "1,248" },
    { key: "staff", value: "86" },
    { key: "attendance", value: "94%" },
    { key: "fees", value: formatSantim(128_450_000, { withCurrency: false }) },
  ] as const;
  return (
    <Screen colors={colors} testID="design-dashboard">
      <PageHeader
        colors={colors}
        title={t("design.dash.title")}
        subtitle={t("design.dash.subtitle")}
        actions={<Button colors={colors} secondary label={t("design.dash.export")} onPress={() => undefined} />}
      />
      <View style={styles.grid}>
        {stats.map((stat) => (
          <Card key={stat.key} colors={colors} style={styles.statCard}>
            <Text style={[styles.statLabel, { color: colors.mutedForeground }]}>
              {t(`design.dash.${stat.key}` as UiKey)}
            </Text>
            <Text style={[styles.statValue, { color: colors.foreground }]}>{stat.value}</Text>
          </Card>
        ))}
      </View>
      <Card colors={colors} style={styles.listCard}>
        <SectionTitle colors={colors}>{t("design.dash.recent")}</SectionTitle>
        {ROWS.map((row) => (
          <ListRow key={row.id} colors={colors} title={row.name} subtitle={row.amharic} right={<Text style={[styles.date, { color: colors.mutedForeground }]}>{row.updated}</Text>} />
        ))}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space.sm,
    paddingHorizontal: space.base,
    paddingVertical: space.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  barTitle: { flex: 1, fontSize: text.md, fontWeight: "600", fontFamily: font.family },
  controls: { flexDirection: "row", gap: space.xs },
  toggle: {
    minHeight: touch,
    justifyContent: "center",
    paddingHorizontal: space.md,
    borderRadius: radius.pill,
  },
  toggleLabel: { fontSize: text.sm, fontWeight: "500", fontFamily: font.family },
  segmentWrap: { paddingHorizontal: space.base, paddingTop: space.md },
  gapXs: { gap: space.xs },
  gapSm: { gap: space.sm },
  fieldLabel: { fontSize: text.sm, fontWeight: "500", fontFamily: font.family },
  listCard: { padding: 0, gap: 0, overflow: "hidden" },
  formRoot: { flex: 1 },
  action: { flex: 1 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space.md },
  statCard: { width: "47%", flexGrow: 1, gap: space.xs },
  statLabel: { fontSize: text.sm, fontFamily: font.family },
  statValue: { fontSize: text.lg, fontWeight: "600", fontFamily: font.family },
  date: { fontSize: text.xs, fontFamily: font.family },
});
