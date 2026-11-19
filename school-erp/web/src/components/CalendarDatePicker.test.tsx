import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CalendarDatePicker } from "./CalendarDatePicker";
import { I18nProvider } from "../providers/I18nProvider";

const messages: Record<string, string> = {
  "calendar.date": "Date",
  "calendar.display": "Show dates in",
  "calendar.ethiopian": "Ethiopian",
  "calendar.gregorian": "Gregorian",
  "calendar.both": "Both",
  "calendar.empty": "Choose a date",
  "calendar.ethiopianValue": "Ethiopian: {{year}}-{{month}}-{{day}}",
};

function renderPicker(props: Partial<Parameters<typeof CalendarDatePicker>[0]> = {}) {
  return render(
    <I18nProvider initialMessages={messages}>
      <CalendarDatePicker value="2024-09-11" onChange={() => {}} {...props} />
    </I18nProvider>,
  );
}

describe("CalendarDatePicker", () => {
  it("shows the Ethiopian and Gregorian forms of a stored ISO date", () => {
    renderPicker();
    expect(screen.getByTestId("date-picker-display")).toHaveTextContent(
      /Meskerem 1, 2017 \(11 Sept? 2024\)/,
    );
    expect(screen.getByTestId("date-picker-ethiopian")).toHaveTextContent(
      "Ethiopian: 2017-1-1",
    );
  });

  it("switches display preference and reports the Gregorian ISO value", () => {
    const onPreferenceChange = vi.fn();
    const onChange = vi.fn();
    renderPicker({ onPreferenceChange, onChange });
    fireEvent.change(screen.getByTestId("date-picker-preference"), {
      target: { value: "ethiopian" },
    });
    expect(onPreferenceChange).toHaveBeenCalledWith("ethiopian");
    fireEvent.change(screen.getByTestId("date-picker-input"), {
      target: { value: "2024-09-12" },
    });
    expect(onChange).toHaveBeenCalledWith("2024-09-12");
  });
});
