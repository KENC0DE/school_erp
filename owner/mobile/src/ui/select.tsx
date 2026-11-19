import type { ReactNativeTheme } from "@erp/tokens";
import { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { font, radius, space, text, touch, weight } from "./tokens";

type Palette = ReactNativeTheme["colors"];

export interface SelectOption {
  value: string;
  label: string;
}

export function SelectField({
  colors,
  label,
  value,
  options,
  onChange,
  placeholder,
  testID,
  disabled = false,
}: {
  colors: Palette;
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  testID?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.value === value);

  return (
    <View style={styles.field}>
      <Text style={[styles.label, { color: colors.foreground }]}>{label}</Text>
      <Pressable
        testID={testID}
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityValue={{ text: selected?.label ?? placeholder ?? "" }}
        accessibilityState={{ disabled, expanded: open }}
        disabled={disabled}
        onPress={() => setOpen(true)}
        style={[
          styles.control,
          {
            backgroundColor: colors.card,
            borderColor: colors.input,
            opacity: disabled ? 0.55 : 1,
          },
        ]}
      >
        <Text
          numberOfLines={1}
          style={[
            styles.controlLabel,
            { color: selected ? colors.foreground : colors.mutedForeground },
          ]}
        >
          {selected?.label ?? placeholder ?? ""}
        </Text>
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <View style={styles.modalRoot}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={placeholder ?? label}
            style={[styles.backdrop, { backgroundColor: colors.foreground, opacity: 0.45 }]}
            onPress={() => setOpen(false)}
          />
          <View
            style={[styles.sheet, { backgroundColor: colors.popover, borderColor: colors.border }]}
          >
            <Text style={[styles.sheetTitle, { color: colors.foreground }]}>{label}</Text>
            <ScrollView style={styles.options}>
              {options.map((option) => {
                const active = option.value === value;
                return (
                  <Pressable
                    key={option.value}
                    testID={testID ? `${testID}-option-${option.value}` : undefined}
                    accessibilityRole="button"
                    accessibilityState={{ selected: active }}
                    onPress={() => {
                      onChange(option.value);
                      setOpen(false);
                    }}
                    style={[
                      styles.option,
                      { borderBottomColor: colors.border },
                      active && { backgroundColor: colors.secondary },
                    ]}
                  >
                    <Text style={[styles.optionLabel, { color: colors.foreground }]}>
                      {option.label}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: space.xs },
  label: {
    fontSize: text.sm,
    fontWeight: weight.medium,
    fontFamily: font.family,
  },
  control: {
    minHeight: touch,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    justifyContent: "center",
  },
  controlLabel: { fontSize: text.base, fontFamily: font.family },
  modalRoot: { flex: 1, justifyContent: "flex-end" },
  backdrop: { ...StyleSheet.absoluteFill },
  sheet: {
    maxHeight: "70%",
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    borderWidth: 1,
    padding: space.base,
    gap: space.md,
  },
  sheetTitle: {
    fontSize: text.base,
    fontWeight: weight.semibold,
    fontFamily: font.family,
  },
  options: { flexGrow: 0 },
  option: {
    minHeight: touch,
    justifyContent: "center",
    paddingHorizontal: space.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  optionLabel: { fontSize: text.base, fontFamily: font.family },
});
