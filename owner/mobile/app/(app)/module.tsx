import { useLocalSearchParams } from "expo-router";
import { ScrollView, StyleSheet, Text } from "react-native";

import { useSchoolI18n } from "../../src/i18n/SchoolI18nContext";
import { useSchoolThemeContext } from "../../src/theme/SchoolThemeContext";
import { Card, Title } from "../../src/ui/primitives";

export default function ModulePlaceholderScreen() {
  const params = useLocalSearchParams<{ path?: string; labelKey?: string }>();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;
  const label = typeof params.labelKey === "string" ? t(params.labelKey) : "";

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Title colors={colors}>{label}</Title>
      <Card colors={colors} style={styles.card}>
        <Text style={[styles.body, { color: colors.foreground }]}>{t("shell.moduleUnavailable")}</Text>
        <Text style={[styles.body, { color: colors.mutedForeground }]}>
          {t("shell.moduleUnavailableBody")}
        </Text>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 12 },
  card: { gap: 10 },
  body: { fontSize: 15, lineHeight: 22 },
});
