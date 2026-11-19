import { View } from "react-native";

import type { Locale } from "../i18n/ui-messages";
import { UI_MESSAGES } from "../i18n/ui-messages";
import { Field, Muted } from "../ui/primitives";
import type { Palette } from "../ui/primitives";

export interface NameValue {
  given_name_en: string;
  father_name_en: string;
  grandfather_name_en: string;
  given_name_am: string;
  father_name_am: string;
  grandfather_name_am: string;
}

export const EMPTY_NAME: NameValue = {
  given_name_en: "",
  father_name_en: "",
  grandfather_name_en: "",
  given_name_am: "",
  father_name_am: "",
  grandfather_name_am: "",
};

type Part = "given" | "father" | "grandfather";

/** Three-part names in both scripts; no "last name" field anywhere (ARCH §5.8). */
export function NameFields({
  colors,
  locale,
  value,
  onChange,
}: {
  colors: Palette;
  locale: Locale;
  value: NameValue;
  onChange: (value: NameValue) => void;
}) {
  const messages: Record<string, string> = UI_MESSAGES[locale];
  const t = (key: string) => messages[key] ?? key;
  const set = (field: keyof NameValue) => (next: string) => onChange({ ...value, [field]: next });

  const group = (script: "en" | "am") => (
    <View>
      {(["given", "father", "grandfather"] as Part[]).map((part) => {
        const field = `${part}_name_${script}` as keyof NameValue;
        return (
          <Field
            key={field}
            colors={colors}
            label={t(`name.${part}${script === "am" ? ".am" : ""}`)}
            testID={`name-${field}`}
            value={value[field]}
            onChangeText={set(field)}
          />
        );
      })}
    </View>
  );

  return (
    <View testID="name-fields">
      <Muted colors={colors}>{t("name.hint")}</Muted>
      <Muted colors={colors}>{t("name.latin")}</Muted>
      {group("en")}
      <Muted colors={colors}>{t("name.amharic")}</Muted>
      {group("am")}
      <Muted colors={colors}>{t("name.no_last_name")}</Muted>
    </View>
  );
}
