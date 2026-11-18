import {
  formatDual,
  formatEthiopian,
  gregorianToEthiopian,
  parseIsoDate,
  type CalendarPreference,
} from "@erp/calendar";

import { cn } from "./cn";
import { Input } from "./input";

export interface DatePickerProps {
  value: string;
  onChange: (isoDate: string) => void;
  preference?: CalendarPreference;
  onPreferenceChange?: (preference: CalendarPreference) => void;
  label?: string;
  locale?: string;
  emptyLabel?: string;
  preferenceLabel?: string;
  preferenceOptions?: Record<CalendarPreference, string>;
  ethiopianValueLabel?: (parts: { year: number; month: number; day: number }) => string;
  testId?: string;
  className?: string;
}

const DEFAULTS: Record<CalendarPreference, string> = {
  ethiopian: "Ethiopian",
  gregorian: "Gregorian",
  both: "Both",
};

/**
 * Stores Gregorian ISO (YYYY-MM-DD) and displays the date in the chosen
 * calendar. Conversion lives in @erp/calendar, never here.
 */
export function DatePicker({
  value,
  onChange,
  preference = "both",
  onPreferenceChange,
  label,
  locale = "en",
  emptyLabel = "No date selected",
  preferenceLabel = "Display",
  preferenceOptions = DEFAULTS,
  ethiopianValueLabel,
  testId = "date-picker",
  className,
}: DatePickerProps) {
  const parsed = parseIsoDate(value);
  const ethiopian = parsed ? gregorianToEthiopian(parsed) : null;

  return (
    <div className={cn("ui-datepicker", className)} data-testid={testId}>
      <label className="ui-field" htmlFor={`${testId}-input`}>
        {label ? <span className="ui-label">{label}</span> : null}
        <Input
          id={`${testId}-input`}
          type="date"
          data-testid={`${testId}-input`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      {onPreferenceChange ? (
        <label className="ui-field" htmlFor={`${testId}-preference`}>
          <span className="ui-help">{preferenceLabel}</span>
          <select
            id={`${testId}-preference`}
            className="ui-select"
            data-testid={`${testId}-preference`}
            value={preference}
            onChange={(event) => onPreferenceChange(event.target.value as CalendarPreference)}
          >
            {(Object.keys(preferenceOptions) as CalendarPreference[]).map((option) => (
              <option key={option} value={option}>
                {preferenceOptions[option]}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <p className="ui-datepicker__alt" data-testid={`${testId}-display`}>
        {parsed && ethiopian
          ? preference === "ethiopian"
            ? formatEthiopian(ethiopian, locale)
            : formatDual(parsed, preference, locale)
          : emptyLabel}
      </p>
      {preference !== "gregorian" && ethiopian && ethiopianValueLabel ? (
        <p className="ui-help" data-testid={`${testId}-ethiopian`}>
          {ethiopianValueLabel(ethiopian)}
        </p>
      ) : null}
    </div>
  );
}
