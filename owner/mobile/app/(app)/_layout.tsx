import { Redirect, Slot, usePathname, useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useApp } from "../../src/context/AppContext";
import type { VerifiedProfile } from "../../src/directory/types";
import {
  SchoolNavigationProvider,
  useSchoolNavigationContext,
} from "../../src/hooks/SchoolNavigationContext";
import { SchoolI18nProvider, useSchoolI18n } from "../../src/i18n/SchoolI18nContext";
import { LOCALES, translateUi, type Locale } from "../../src/i18n/ui-messages";
import { SchoolThemeProvider, useSchoolThemeContext } from "../../src/theme/SchoolThemeContext";
import type { NavItem } from "../../src/session/session";
import { defaultNativeTheme } from "../../src/theme/nativeTheme";
import {
  BottomTabs,
  Button,
  Divider,
  ListRow,
  Segmented,
  Sheet,
  font,
  space,
  text,
  type TabItem,
} from "../../src/ui";

/** Bottom tabs stay at five including "More"; the rest live in the sheet. */
const MAX_TABS = 4;

function navigateTo(router: ReturnType<typeof useRouter>, item: NavItem): void {
  if (item.path === "/") {
    router.push("/(app)");
  } else if (item.path === "/students") {
    router.push("/(app)/students");
  } else if (item.path === "/staff") {
    router.push("/(app)/staff");
  } else if (item.path === "/attendance") {
    router.push("/(app)/attendance");
  } else if (item.path === "/sample") {
    router.push("/(app)/sample");
  } else {
    router.push({ pathname: "/(app)/module", params: { path: item.path, labelKey: item.label_key } });
  }
}

function Shell({ profile }: { profile: VerifiedProfile }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, locale, mode, setLocale, setMode, signOut } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const { navigation, loading, error, reload } = useSchoolNavigationContext();
  const colors = rn.colors;
  const ui = (key: Parameters<typeof translateUi>[1]) => translateUi(locale, key);
  const [moreOpen, setMoreOpen] = useState(false);

  const items = navigation?.items ?? [];
  const isActive = (item: NavItem) =>
    item.path === "/"
      ? pathname === "/" || pathname === ""
      : pathname === item.path || pathname.startsWith(`${item.path}/`);

  const visible = items.slice(0, MAX_TABS);
  const overflow = items.slice(MAX_TABS);
  const tabs: TabItem[] = [
    ...visible.map((item) => ({
      key: item.key,
      label: t(item.label_key),
      active: !moreOpen && isActive(item),
      onPress: () => navigateTo(router, item),
    })),
    {
      key: "more",
      label: ui("shell.more"),
      active: moreOpen || overflow.some(isActive),
      onPress: () => setMoreOpen(true),
    },
  ];

  async function logout(): Promise<void> {
    await signOut();
    router.replace("/login");
  }

  return (
    <SafeAreaView
      edges={["top", "left", "right"]}
      style={[styles.shell, { backgroundColor: colors.background }]}
    >
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <View style={styles.headerText}>
          <Text numberOfLines={1} style={[styles.schoolName, { color: colors.foreground }]}>
            {profile.name}
          </Text>
          <Text numberOfLines={1} style={[styles.muted, { color: colors.mutedForeground }]}>
            {user?.display_name ?? ""}
          </Text>
        </View>
      </View>

      <View style={styles.content}>
        {loading && items.length === 0 ? (
          <View style={styles.center}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : (
          <Slot />
        )}
      </View>

      <BottomTabs colors={colors} items={tabs} />

      <Sheet
        visible={moreOpen}
        onClose={() => setMoreOpen(false)}
        title={ui("shell.menu")}
        closeLabel={ui("shell.close")}
        colors={colors}
      >
        {overflow.map((item) => (
          <ListRow
            key={item.key}
            colors={colors}
            title={t(item.label_key)}
            onPress={() => {
              setMoreOpen(false);
              navigateTo(router, item);
            }}
          />
        ))}
        {__DEV__ ? (
          <ListRow
            colors={colors}
            title={ui("design.title")}
            subtitle={ui("design.tab.list")}
            onPress={() => {
              setMoreOpen(false);
              router.push("/design");
            }}
          />
        ) : null}
        {error ? (
          <View style={styles.section}>
            <Button colors={colors} secondary label={ui("common.retry")} onPress={() => void reload()} />
          </View>
        ) : null}
        <Divider colors={colors} style={styles.sectionGap} />
        <View style={styles.section}>
          <Text style={[styles.sectionLabel, { color: colors.mutedForeground }]}>
            {ui("shell.language")}
          </Text>
          <Segmented
            colors={colors}
            items={LOCALES.map((code: Locale) => ({
              key: code,
              label: ui(code === "en" ? "language.en" : "language.am"),
              active: locale === code,
              onPress: () => void setLocale(code),
            }))}
          />
        </View>
        <View style={styles.section}>
          <Text style={[styles.sectionLabel, { color: colors.mutedForeground }]}>
            {ui("shell.theme")}
          </Text>
          <Button
            colors={colors}
            secondary
            label={ui(mode === "light" ? "shell.dark" : "shell.light")}
            onPress={() => void setMode(mode === "light" ? "dark" : "light")}
          />
        </View>
        <View style={styles.section}>
          <Button colors={colors} danger label={ui("shell.logout")} onPress={() => void logout()} />
        </View>
      </Sheet>
    </SafeAreaView>
  );
}

function AppShell() {
  const { ready, profile, user, locale, mode } = useApp();
  const loadingColors = useMemo(() => defaultNativeTheme(mode).colors, [mode]);

  if (!ready) {
    return (
      <View style={[styles.shell, styles.center, { backgroundColor: loadingColors.background }]}>
        <ActivityIndicator color={loadingColors.primary} />
      </View>
    );
  }
  if (!profile) return <Redirect href="/" />;
  if (!user) return <Redirect href="/login" />;

  return (
    <SchoolThemeProvider profile={profile} mode={mode}>
      <SchoolI18nProvider profile={profile} locale={locale}>
        <SchoolNavigationProvider profile={profile}>
          <Shell profile={profile} />
        </SchoolNavigationProvider>
      </SchoolI18nProvider>
    </SchoolThemeProvider>
  );
}

export default function AppLayout() {
  return <AppShell />;
}

const styles = StyleSheet.create({
  shell: { flex: 1 },
  center: { alignItems: "center", justifyContent: "center" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: space.base,
    paddingVertical: space.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: space.md,
  },
  headerText: { flex: 1 },
  schoolName: { fontSize: text.md, fontWeight: "600", fontFamily: font.family },
  muted: { fontSize: text.xs, marginTop: 2, fontFamily: font.family },
  content: { flex: 1 },
  section: { gap: space.sm, paddingTop: space.sm },
  sectionGap: { marginTop: space.md },
  sectionLabel: { fontSize: text.sm, fontFamily: font.family },
});
