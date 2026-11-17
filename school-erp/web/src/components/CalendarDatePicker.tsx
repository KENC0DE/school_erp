import {
  formatDual,
  formatEthiopian,
  gregorianToEthiopian,
  parseIsoDate,
  type CalendarPreference,
} from "@erp/calendar";

import { Input } from "./ui/Input";
import { useI18n } from "../providers/I18nProvider";

const PREFERENCES: CalendarPreference[] = ["ethiopian", "gregorian", "both"];

/**
 * Stores Gregorian ISO (YYYY-MM-DD) and displays the date in the chosen
 * calendar. Ethiopian conversion lives in @erp/calendar, never here.
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
  const parsed = parseIsoDate(value);
  const ethiopian = parsed ? gregorianToEthiopian(parsed) : null;

  return (
    <div className="space-y-2" data-testid={testId}>
      <label className="block space-y-1 text-sm">
        <span className="text-muted-foreground">{label ?? t("calendar.date")}</span>
        <Input
          type="date"
          data-testid={`${testId}-input`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      {onPreferenceChange ? (
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">{t("calendar.display")}</span>
          <select
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            data-testid={`${testId}-preference`}
            value={preference}
            onChange={(event) => onPreferenceChange(event.target.value as CalendarPreference)}
          >
            {PREFERENCES.map((option) => (
              <option key={option} value={option}>
                {t(`calendar.${option}`)}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <p className="text-sm text-foreground" data-testid={`${testId}-display`}>
        {parsed && ethiopian
          ? preference === "ethiopian"
            ? formatEthiopian(ethiopian, locale)
            : formatDual(parsed, preference, locale)
          : t("calendar.empty")}
      </p>
      {preference !== "gregorian" && ethiopian ? (
        <p className="text-xs text-muted-foreground" data-testid={`${testId}-ethiopian`}>
          {t("calendar.ethiopianValue", {
            year: ethiopian.year,
            month: ethiopian.month,
            day: ethiopian.day,
          })}
        </p>
      ) : null}
    </div>
  );
}
