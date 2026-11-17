import { ScrollView, StyleSheet, Text, View } from "react-native";

import { useApp } from "../../src/context/AppContext";
import { useSchoolNavigationContext } from "../../src/hooks/SchoolNavigationContext";
import { useSchoolI18n } from "../../src/i18n/SchoolI18nContext";
import { useSchoolThemeContext } from "../../src/theme/SchoolThemeContext";
import { Card, Title } from "../../src/ui/primitives";

export default function DashboardScreen() {
  const { user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const { navigation } = useSchoolNavigationContext();
  const colors = rn.colors;

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Title colors={colors}>{t("dashboard.title")}</Title>
      <Text style={[styles.welcome, { color: colors.foreground }]}>
        {t("dashboard.welcome", { name: user?.display_name ?? "" })}
      </Text>
      <Text style={[styles.body, { color: colors.mutedForeground }]}>{t("dashboard.subtitle")}</Text>

      <Card colors={colors} style={styles.card}>
        <Text style={[styles.section, { color: colors.foreground }]}>{t("dashboard.modules")}</Text>
        <View style={styles.chips}>
          {(navigation?.modules ?? []).map((moduleKey) => (
            <View key={moduleKey} style={[styles.chip, { backgroundColor: colors.muted }]}>
              <Text style={{ color: colors.foreground }}>{moduleKey}</Text>
            </View>
          ))}
        </View>
      </Card>

      <Card colors={colors} style={styles.card}>
        <Text style={[styles.body, { color: colors.mutedForeground }]}>
          {t("dashboard.language_hint")}
        </Text>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 40, gap: 12 },
  welcome: { fontSize: 18, fontWeight: "600" },
  body: { fontSize: 15, lineHeight: 22 },
  section: { fontSize: 16, fontWeight: "700", marginBottom: 10 },
  card: { marginTop: 4 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999 },
});
