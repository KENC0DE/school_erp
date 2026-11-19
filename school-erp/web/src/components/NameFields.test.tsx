import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EMPTY_NAME, NameFields } from "./NameFields";
import { I18nProvider } from "../providers/I18nProvider";

const messages: Record<string, string> = {
  "name.title": "Full name",
  "name.hint": "Fill in both scripts when you can; certificates usually use Amharic.",
  "name.latin": "Latin script",
  "name.amharic": "Amharic script",
  "name.given": "Given name",
  "name.father": "Father's name",
  "name.grandfather": "Grandfather's name",
  "name.given.am": "የራስ ስም",
  "name.father.am": "የአባት ስም",
  "name.grandfather.am": "የአያት ስም",
  "name.no_last_name": "Ethiopian names have no last name: given, father, grandfather.",
};

describe("NameFields", () => {
  it("offers three fields per script and never asks for a last name", () => {
    render(
      <I18nProvider initialMessages={messages}>
        <NameFields value={EMPTY_NAME} onChange={() => {}} />
      </I18nProvider>,
    );
    for (const field of [
      "given_name_en",
      "father_name_en",
      "grandfather_name_en",
      "given_name_am",
      "father_name_am",
      "grandfather_name_am",
    ]) {
      expect(screen.getByTestId(`name-${field}`)).toBeInTheDocument();
    }
    expect(screen.queryByText(/last name/i)).toHaveTextContent(/no last name/i);
  });

  it("reports edits with both scripts intact", () => {
    const onChange = vi.fn();
    render(
      <I18nProvider initialMessages={messages}>
        <NameFields value={EMPTY_NAME} onChange={onChange} />
      </I18nProvider>,
    );
    fireEvent.change(screen.getByTestId("name-given_name_en"), { target: { value: "Abebe" } });
    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_NAME, given_name_en: "Abebe" });
    fireEvent.change(screen.getByTestId("name-father_name_am"), { target: { value: "ከበደ" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY_NAME, father_name_am: "ከበደ" });
  });
});
