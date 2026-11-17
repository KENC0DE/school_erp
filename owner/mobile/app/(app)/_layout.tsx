import { Redirect, Slot, usePathname, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useMemo } from "react";
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
import { Button } from "../../src/ui/primitives";

function navigateTo(router: ReturnType<typeof useRouter>, item: NavItem): void {
  if (item.path === "/") {
    router.push("/(app)");
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

  const items = navigation?.items ?? [];
  const isActive = (item: NavItem) =>
    item.path === "/" ? pathname === "/" || pathname === "" : pathname === item.path;

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
          <Text style={[styles.schoolName, { color: colors.foreground }]}>{profile.name}</Text>
          <Text style={[styles.muted, { color: colors.mutedForeground }]}>{user?.display_name ?? ""}</Text>
        </View>
        <View style={styles.controls}>
          {LOCALES.map((code: Locale) => (
            <Pressable
              key={code}
              accessibilityRole="button"
              onPress={() => void setLocale(code)}
              style={[
                styles.chip,
                { backgroundColor: locale === code ? colors.primary : colors.secondary },
              ]}
            >
              <Text style={{ color: locale === code ? colors.primaryForeground : colors.foreground }}>
                {ui(code === "en" ? "language.en" : "language.am")}
              </Text>
            </Pressable>
          ))}
          <Pressable
            accessibilityRole="button"
            onPress={() => void setMode(mode === "light" ? "dark" : "light")}
            style={[styles.chip, { backgroundColor: colors.secondary }]}
          >
            <Text style={{ color: colors.foreground }}>
              {ui(mode === "light" ? "shell.light" : "shell.dark")}
            </Text>
          </Pressable>
        </View>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.nav} contentContainerStyle={styles.navContent}>
        {loading && items.length === 0 ? <ActivityIndicator color={colors.primary} /> : null}
        {items.map((item) => (
          <Pressable
            key={item.key}
            accessibilityRole="button"
            onPress={() => navigateTo(router, item)}
            style={[
              styles.navItem,
              {
                borderBottomColor: isActive(item) ? colors.primary : "transparent",
              },
            ]}
          >
            <Text
              style={[
                styles.navLabel,
                { color: isActive(item) ? colors.primary : colors.mutedForeground },
              ]}
            >
              {t(item.label_key)}
            </Text>
          </Pressable>
        ))}
        {error ? (
          <Button colors={colors} secondary label={ui("common.retry")} onPress={() => void reload()} />
        ) : null}
      </ScrollView>

      <View style={styles.content}>
        <Slot />
      </View>

      <View style={[styles.footer, { borderTopColor: colors.border }]}>
        <Button colors={colors} secondary label={ui("shell.logout")} onPress={() => void logout()} />
      </View>
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
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderBottomWidth: 1,
    gap: 12,
  },
  headerText: { flex: 1 },
  schoolName: { fontSize: 17, fontWeight: "700" },
  muted: { fontSize: 12, marginTop: 2 },
  controls: { flexDirection: "row", gap: 6, alignItems: "center" },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999 },
  nav: { flexGrow: 0 },
  navContent: { paddingHorizontal: 14, paddingVertical: 8, gap: 14, alignItems: "center" },
  navItem: { paddingVertical: 6, borderBottomWidth: 2 },
  navLabel: { fontSize: 14, fontWeight: "600" },
  content: { flex: 1 },
  footer: { padding: 14, borderTopWidth: 1 },
});
