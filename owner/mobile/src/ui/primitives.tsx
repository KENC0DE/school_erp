import type { ReactNativeTheme } from "@erp/tokens";
import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { font, radius, space, text, touch, weight } from "./tokens";

export type Palette = ReactNativeTheme["colors"];

export function SafeScreen({ colors, children }: { colors: Palette; children: ReactNode }) {
  return (
    <SafeAreaView style={[styles.flex, { backgroundColor: colors.background }]}>
      {children}
    </SafeAreaView>
  );
}

export function Screen({
  colors,
  children,
  style,
}: {
  colors: Palette;
  children: ReactNode;
  style?: ViewStyle;
}) {
  return (
    <View style={[styles.flex, { backgroundColor: colors.background }, style]}>{children}</View>
  );
}

export function Title({ colors, children }: { colors: Palette; children: ReactNode }) {
  return (
    <Text accessibilityRole="header" style={[styles.title, { color: colors.foreground }]}>
      {children}
    </Text>
  );
}

export function Muted({ colors, children }: { colors: Palette; children: ReactNode }) {
  return <Text style={[styles.muted, { color: colors.mutedForeground }]}>{children}</Text>;
}

export function Button({
  colors,
  label,
  onPress,
  busy = false,
  disabled = false,
  secondary = false,
  danger = false,
}: {
  colors: Palette;
  label: string;
  onPress: () => void;
  busy?: boolean;
  disabled?: boolean;
  secondary?: boolean;
  danger?: boolean;
}) {
  const isDisabled = disabled || busy;
  const background = danger ? colors.destructive : secondary ? colors.secondary : colors.primary;
  const foreground = danger
    ? colors.destructiveForeground
    : secondary
      ? colors.foreground
      : colors.primaryForeground;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: isDisabled, busy }}
      disabled={isDisabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: background, opacity: isDisabled ? 0.55 : pressed ? 0.82 : 1 },
      ]}
    >
      {busy ? (
        <ActivityIndicator color={foreground} />
      ) : (
        <Text style={[styles.buttonLabel, { color: foreground }]}>{label}</Text>
      )}
    </Pressable>
  );
}

export function Field({
  colors,
  label,
  hint,
  required = false,
  ...props
}: TextInputProps & { colors: Palette; label: string; hint?: string; required?: boolean }) {
  return (
    <View style={styles.field}>
      <Text style={[styles.label, { color: colors.foreground }]}>
        {label}
        {required ? (
          <Text style={{ color: colors.destructive }} accessibilityLabel={label}>
            {" *"}
          </Text>
        ) : null}
      </Text>
      <TextInput
        {...props}
        accessibilityLabel={props.accessibilityLabel ?? label}
        placeholderTextColor={colors.mutedForeground}
        style={[
          styles.input,
          { color: colors.foreground, borderColor: colors.input, backgroundColor: colors.card },
          props.style,
        ]}
      />
      {hint ? (
        <Text style={[styles.hint, { color: colors.mutedForeground }]}>{hint}</Text>
      ) : null}
    </View>
  );
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

const styles = StyleSheet.create({
  flex: { flex: 1 },
  title: { fontSize: text.xl, fontWeight: weight.semibold, fontFamily: font.family },
  muted: { fontSize: text.sm, lineHeight: 21, fontFamily: font.family },
  button: {
    minHeight: touch,
    borderRadius: radius.md,
    paddingVertical: space.md,
    paddingHorizontal: space.base,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonLabel: { fontSize: text.base, fontWeight: weight.semibold, fontFamily: font.family },
  field: { gap: space.xs },
  label: { fontSize: text.sm, fontWeight: weight.medium, fontFamily: font.family },
  input: {
    minHeight: touch,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.md,
    fontSize: text.base,
    fontFamily: font.family,
  },
  hint: { fontSize: text.xs, lineHeight: 18, fontFamily: font.family },
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
});
