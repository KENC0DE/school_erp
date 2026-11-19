import type { ReactNativeTheme } from "@erp/tokens";
import type { ReactNode } from "react";
import { ScrollView, StyleSheet, Text, View, type ViewStyle } from "react-native";

import { font, radius, space, text, weight } from "./tokens";

export type Palette = ReactNativeTheme["colors"];

export function Screen({
  colors,
  children,
  style,
  scroll = true,
  testID,
}: {
  colors: Palette;
  children: ReactNode;
  style?: ViewStyle;
  scroll?: boolean;
  testID?: string;
}) {
  if (!scroll) {
    return (
      <View testID={testID} style={[styles.screen, { backgroundColor: colors.background }, style]}>
        {children}
      </View>
    );
  }
  return (
    <ScrollView
      testID={testID}
      style={[styles.flex, { backgroundColor: colors.background }]}
      contentContainerStyle={[styles.content, style]}
      keyboardShouldPersistTaps="handled"
    >
      {children}
    </ScrollView>
  );
}

export function PageHeader({
  colors,
  title,
  subtitle,
  actions,
}: {
  colors: Palette;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <View style={styles.header}>
      <View style={styles.headerText}>
        <Text accessibilityRole="header" style={[styles.title, { color: colors.foreground }]}>
          {title}
        </Text>
        {subtitle ? (
          <Text style={[styles.subtitle, { color: colors.mutedForeground }]}>{subtitle}</Text>
        ) : null}
      </View>
      {actions}
    </View>
  );
}

export function SectionTitle({ colors, children }: { colors: Palette; children: ReactNode }) {
  return <Text style={[styles.sectionTitle, { color: colors.foreground }]}>{children}</Text>;
}

export function Card({
  colors,
  children,
  style,
}: {
  colors: Palette;
  children: ReactNode;
  style?: ViewStyle;
}) {
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: colors.card, borderColor: colors.border, shadowColor: colors.foreground },
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function Row({
  colors,
  label,
  value,
  last = false,
}: {
  colors: Palette;
  label: string;
  value: ReactNode;
  last?: boolean;
}) {
  return (
    <View
      style={[
        styles.row,
        { borderBottomColor: colors.border },
        last && styles.rowLast,
      ]}
    >
      <Text style={[styles.rowLabel, { color: colors.mutedForeground }]}>{label}</Text>
      <View style={styles.rowValue}>
        {typeof value === "string" ? (
          <Text style={[styles.rowValueText, { color: colors.foreground }]}>{value}</Text>
        ) : (
          value
        )}
      </View>
    </View>
  );
}

export function Divider({ colors, style }: { colors: Palette; style?: ViewStyle }) {
  return <View style={[styles.divider, { backgroundColor: colors.border }, style]} />;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  screen: { flex: 1 },
  content: { padding: space.base, gap: space.base, paddingBottom: space.xl },
  header: { gap: space.md },
  headerText: { gap: space.xs },
  title: { fontSize: text.xl, fontWeight: weight.semibold, fontFamily: font.family },
  subtitle: { fontSize: text.sm, lineHeight: 21, fontFamily: font.family },
  sectionTitle: { fontSize: text.base, fontWeight: weight.semibold, fontFamily: font.family },
  card: {
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.base,
    gap: space.md,
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space.base,
    paddingVertical: space.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  rowLast: { borderBottomWidth: 0, paddingBottom: 0 },
  rowLabel: { fontSize: text.sm, fontFamily: font.family, flexShrink: 0 },
  rowValue: { flexShrink: 1, alignItems: "flex-end" },
  rowValueText: { fontSize: text.base, fontWeight: weight.medium, fontFamily: font.family },
  divider: { height: StyleSheet.hairlineWidth, width: "100%" },
});
