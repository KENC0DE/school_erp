import type { ReactNativeTheme } from "@erp/tokens";
import type { ReactNode } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { font, radius, space, text, touch, weight } from "./tokens";

type Palette = ReactNativeTheme["colors"];

export function ListRow({
  colors,
  title,
  subtitle,
  right,
  onPress,
  testID,
}: {
  colors: Palette;
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onPress?: () => void;
  testID?: string;
}) {
  return (
    <Pressable
      testID={testID}
      accessibilityRole={onPress ? "button" : undefined}
      accessibilityLabel={subtitle ? `${title}, ${subtitle}` : title}
      disabled={!onPress}
      onPress={onPress}
      style={({ pressed }) => [
        styles.listRow,
        {
          backgroundColor: pressed && onPress ? colors.secondary : colors.card,
          borderBottomColor: colors.border,
        },
      ]}
    >
      <View style={styles.listRowText}>
        <Text style={[styles.listRowTitle, { color: colors.foreground }]}>{title}</Text>
        {subtitle ? (
          <Text style={[styles.listRowSubtitle, { color: colors.mutedForeground }]}>{subtitle}</Text>
        ) : null}
      </View>
      {right}
      {onPress ? (
        <Text accessible={false} style={[styles.chevron, { color: colors.mutedForeground }]}>
          ›
        </Text>
      ) : null}
    </Pressable>
  );
}

export interface TabItem {
  key: string;
  label: string;
  active?: boolean;
  onPress: () => void;
}

export function BottomTabs({ colors, items }: { colors: Palette; items: TabItem[] }) {
  const insets = useSafeAreaInsets();
  return (
    <View
      accessibilityRole="tablist"
      style={[
        styles.tabbar,
        {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          paddingBottom: Math.max(insets.bottom, space.sm),
        },
      ]}
    >
      {items.map((item) => (
        <Pressable
          key={item.key}
          accessibilityRole="tab"
          accessibilityState={{ selected: Boolean(item.active) }}
          accessibilityLabel={item.label}
          onPress={item.onPress}
          style={styles.tab}
        >
          <View
            style={[
              styles.tabDot,
              { backgroundColor: item.active ? colors.primary : "transparent" },
            ]}
          />
          <Text
            numberOfLines={1}
            style={[
              styles.tabLabel,
              {
                color: item.active ? colors.primary : colors.mutedForeground,
                fontWeight: item.active ? weight.semibold : weight.medium,
              },
            ]}
          >
            {item.label}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

export function Sheet({
  visible,
  onClose,
  title,
  closeLabel,
  colors,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  title: string;
  closeLabel: string;
  colors: Palette;
  children: ReactNode;
}) {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalRoot}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={closeLabel}
          style={[styles.backdrop, { backgroundColor: colors.foreground, opacity: 0.45 }]}
          onPress={onClose}
        />
        <View
          style={[
            styles.sheet,
            {
              backgroundColor: colors.popover,
              borderColor: colors.border,
              paddingBottom: Math.max(insets.bottom, space.base),
            },
          ]}
        >
          <View style={styles.sheetHeader}>
            <Text style={[styles.sheetTitle, { color: colors.foreground }]}>{title}</Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={closeLabel}
              onPress={onClose}
              style={styles.closeButton}
            >
              <Text style={[styles.closeLabel, { color: colors.mutedForeground }]}>×</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.sheetBody}>{children}</ScrollView>
        </View>
      </View>
    </Modal>
  );
}

export function Toast({
  colors,
  message,
  tone = "neutral",
  onDismiss,
  dismissLabel,
}: {
  colors: Palette;
  message: string;
  tone?: Tone;
  onDismiss: () => void;
  dismissLabel: string;
}) {
  const background =
    tone === "danger" ? colors.destructive : tone === "success" ? colors.primary : colors.secondary;
  const foreground =
    tone === "danger"
      ? colors.destructiveForeground
      : tone === "success"
        ? colors.primaryForeground
        : colors.secondaryForeground;
  return (
    <View accessibilityRole="alert" style={[styles.toast, { backgroundColor: background }]}>
      <Text style={[styles.toastLabel, { color: foreground }]}>{message}</Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={dismissLabel}
        onPress={onDismiss}
        style={styles.toastClose}
      >
        <Text style={[styles.toastLabel, { color: foreground }]}>×</Text>
      </Pressable>
    </View>
  );
}

export type Tone = "neutral" | "success" | "warning" | "danger";

export function Badge({
  colors,
  tone = "neutral",
  children,
}: {
  colors: Palette;
  tone?: Tone;
  children: ReactNode;
}) {
  const palette =
    tone === "success"
      ? { background: colors.primary, color: colors.primaryForeground }
      : tone === "warning"
        ? { background: colors.accent, color: colors.accentForeground }
        : tone === "danger"
          ? { background: colors.destructive, color: colors.destructiveForeground }
          : { background: colors.secondary, color: colors.secondaryForeground };
  return (
    <View style={[styles.badge, { backgroundColor: palette.background }]}>
      <Text style={[styles.badgeLabel, { color: palette.color }]}>{children}</Text>
    </View>
  );
}

export function SaveBar({ colors, children }: { colors: Palette; children: ReactNode }) {
  const insets = useSafeAreaInsets();
  return (
    <View
      style={[
        styles.savebar,
        {
          backgroundColor: colors.background,
          borderTopColor: colors.border,
          paddingBottom: Math.max(insets.bottom, space.md),
        },
      ]}
    >
      {children}
    </View>
  );
}

export function Skeleton({
  colors,
  height = 16,
  width = "100%",
  style,
}: {
  colors: Palette;
  height?: number;
  width?: number | `${number}%`;
  style?: ViewStyle;
}) {
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[{ height, width, borderRadius: radius.sm, backgroundColor: colors.muted }, style]}
    />
  );
}

export function EmptyState({
  colors,
  title,
  description,
  action,
}: {
  colors: Palette;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <View style={styles.state}>
      <Text style={[styles.stateTitle, { color: colors.foreground }]}>{title}</Text>
      {description ? (
        <Text style={[styles.stateBody, { color: colors.mutedForeground }]}>{description}</Text>
      ) : null}
      {action}
    </View>
  );
}

export function ErrorState({
  colors,
  title,
  description,
  requestId,
  requestIdLabel,
  action,
}: {
  colors: Palette;
  title: string;
  description?: string;
  requestId?: string;
  requestIdLabel?: string;
  action?: ReactNode;
}) {
  return (
    <View accessibilityRole="alert" style={styles.state}>
      <Text style={[styles.stateTitle, { color: colors.foreground }]}>{title}</Text>
      {description ? (
        <Text style={[styles.stateBody, { color: colors.mutedForeground }]}>{description}</Text>
      ) : null}
      {requestId ? (
        <Text style={[styles.stateMeta, { color: colors.mutedForeground }]}>
          {requestIdLabel}: {requestId}
        </Text>
      ) : null}
      {action}
    </View>
  );
}

export function Segmented({
  colors,
  items,
}: {
  colors: Palette;
  items: Array<{ key: string; label: string; active: boolean; onPress: () => void; testID?: string }>;
}) {
  return (
    <View style={[styles.segmented, { backgroundColor: colors.secondary }]}>
      {items.map((item) => (
        <Pressable
          key={item.key}
          testID={item.testID}
          accessibilityRole="button"
          accessibilityState={{ selected: item.active }}
          onPress={item.onPress}
          style={[
            styles.segment,
            item.active && { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <Text
            style={[
              styles.segmentLabel,
              { color: item.active ? colors.foreground : colors.mutedForeground },
            ]}
          >
            {item.label}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  listRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    minHeight: touch,
    paddingVertical: space.md,
    paddingHorizontal: space.base,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  listRowText: { flex: 1, gap: 2 },
  listRowTitle: { fontSize: text.base, fontWeight: weight.medium, fontFamily: font.family },
  listRowSubtitle: { fontSize: text.sm, fontFamily: font.family },
  chevron: { fontSize: text.lg, fontFamily: font.family },
  tabbar: {
    flexDirection: "row",
    alignItems: "stretch",
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: space.sm,
  },
  tab: {
    flex: 1,
    minHeight: touch,
    alignItems: "center",
    justifyContent: "center",
    gap: space.xs,
    paddingHorizontal: space.xs,
  },
  tabDot: { width: 18, height: 3, borderRadius: radius.pill },
  tabLabel: { fontSize: text.xs, fontFamily: font.family, textAlign: "center" },
  modalRoot: { flex: 1, justifyContent: "flex-end" },
  backdrop: { ...StyleSheet.absoluteFill },
  sheet: {
    maxHeight: "85%",
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    paddingTop: space.base,
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: space.base,
    paddingBottom: space.sm,
  },
  sheetTitle: { fontSize: text.md, fontWeight: weight.semibold, fontFamily: font.family },
  closeButton: { minWidth: touch, minHeight: touch, alignItems: "center", justifyContent: "center" },
  closeLabel: { fontSize: text.xl, fontFamily: font.family },
  sheetBody: { paddingHorizontal: space.base, paddingBottom: space.lg, gap: space.sm },
  badge: {
    alignSelf: "flex-start",
    borderRadius: radius.pill,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
  },
  badgeLabel: { fontSize: text.xs, fontWeight: weight.medium, fontFamily: font.family },
  state: { alignItems: "center", gap: space.sm, paddingVertical: space.xl, paddingHorizontal: space.base },
  stateTitle: { fontSize: text.base, fontWeight: weight.semibold, fontFamily: font.family },
  stateBody: { fontSize: text.sm, lineHeight: 21, textAlign: "center", fontFamily: font.family },
  stateMeta: { fontSize: text.xs, fontFamily: font.family },
  savebar: {
    flexDirection: "row",
    gap: space.sm,
    paddingHorizontal: space.base,
    paddingTop: space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  toast: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space.sm,
    borderRadius: radius.md,
    paddingVertical: space.md,
    paddingHorizontal: space.base,
  },
  toastLabel: { fontSize: text.sm, fontFamily: font.family, flexShrink: 1 },
  toastClose: { minWidth: touch, minHeight: touch, alignItems: "center", justifyContent: "center" },
  segmented: { flexDirection: "row", borderRadius: radius.md, padding: space.xs, gap: space.xs },
  segment: {
    flex: 1,
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "transparent",
  },
  segmentLabel: { fontSize: text.sm, fontWeight: weight.medium, fontFamily: font.family },
});
