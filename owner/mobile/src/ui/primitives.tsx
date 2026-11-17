import type { ReactNativeTheme } from "@erp/tokens";
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
import type { ReactNode } from "react";

export type Palette = ReactNativeTheme["colors"];

export function SafeScreen({ colors, children }: { colors: Palette; children: ReactNode }) {
  return <SafeAreaView style={[styles.flex, { backgroundColor: colors.background }]}>{children}</SafeAreaView>;
}

export function Screen({ colors, children, style }: { colors: Palette; children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.flex, { backgroundColor: colors.background }, style]}>{children}</View>;
}

export function Title({ colors, children }: { colors: Palette; children: ReactNode }) {
  return <Text style={[styles.title, { color: colors.foreground }]}>{children}</Text>;
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
}: {
  colors: Palette;
  label: string;
  onPress: () => void;
  busy?: boolean;
  disabled?: boolean;
  secondary?: boolean;
}) {
  const isDisabled = disabled || busy;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={isDisabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        {
          backgroundColor: secondary ? colors.secondary : colors.primary,
          opacity: isDisabled ? 0.55 : pressed ? 0.82 : 1,
        },
      ]}
    >
      {busy ? (
        <ActivityIndicator color={secondary ? colors.foreground : colors.primaryForeground} />
      ) : (
        <Text
          style={[
            styles.buttonLabel,
            { color: secondary ? colors.foreground : colors.primaryForeground },
          ]}
        >
          {label}
        </Text>
      )}
    </Pressable>
  );
}

export function Field({
  colors,
  label,
  ...props
}: TextInputProps & { colors: Palette; label: string }) {
  return (
    <View style={styles.field}>
      <Text style={[styles.label, { color: colors.foreground }]}>{label}</Text>
      <TextInput
        {...props}
        placeholderTextColor={colors.mutedForeground}
        style={[
          styles.input,
          { color: colors.foreground, borderColor: colors.input, backgroundColor: colors.card },
          props.style,
        ]}
      />
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
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }, style]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  title: { fontSize: 28, fontWeight: "700", marginBottom: 8 },
  muted: { fontSize: 15, lineHeight: 22 },
  button: { borderRadius: 10, paddingVertical: 14, paddingHorizontal: 18, alignItems: "center" },
  buttonLabel: { fontSize: 16, fontWeight: "600" },
  field: { marginBottom: 14 },
  label: { fontSize: 14, fontWeight: "600", marginBottom: 6 },
  input: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  card: { borderWidth: 1, borderRadius: 14, padding: 16 },
});
