import { type CalendarPreference } from "@erp/calendar";
import { DatePicker } from "@erp/ui-web";

import { useI18n } from "../providers/I18nProvider";

/**
 * Stores Gregorian ISO (YYYY-MM-DD) and displays the date in the chosen
 * calendar. The picker itself is the shared kit component.
 */
export function CalendarDatePicker({
  value,
  onChange,
  preference = "both",
  onPreferenceChange,
  label,
  testId = "date-picker",
}: {
  value: string;
  onChange: (isoDate: string) => void;
  preference?: CalendarPreference;
  onPreferenceChange?: (preference: CalendarPreference) => void;
  label?: string;
  testId?: string;
}) {
  const { t, locale } = useI18n();
  return (
    <DatePicker
      value={value}
      onChange={onChange}
      preference={preference}
      onPreferenceChange={onPreferenceChange}
      label={label ?? t("calendar.date")}
      locale={locale}
      emptyLabel={t("calendar.empty")}
      preferenceLabel={t("calendar.display")}
      preferenceOptions={{
        ethiopian: t("calendar.ethiopian"),
        gregorian: t("calendar.gregorian"),
        both: t("calendar.both"),
      }}
      ethiopianValueLabel={(parts) =>
        t("calendar.ethiopianValue", { year: parts.year, month: parts.month, day: parts.day })
      }
      testId={testId}
    />
  );
}
