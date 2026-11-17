import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CustomFieldsForm, type CustomFieldDefinition } from "./CustomFieldsForm";
import { I18nProvider } from "../providers/I18nProvider";

const messages: Record<string, string> = {
  "common.error": "Something went wrong",
  "custom.loading": "Loading extra fields…",
  "custom.empty": "No extra fields are configured for this record.",
  "custom.title": "Additional information",
  "custom.optional": "Optional",
  "custom.choose": "Choose…",
  "custom.multiselect.hint": "Choose all that apply",
  "custom.person.blood_group": "Blood group",
  "custom.person.siblings": "Siblings",
  "custom.person.boarding": "Boarding",
  "custom.person.arrival": "Arrival date",
  "custom.person.clubs": "Clubs",
  "custom.person.code": "Student code",
  "error.custom_field.required": "This field is required",
};

function definition(overrides: Partial<CustomFieldDefinition>): CustomFieldDefinition {
  return {
    id: overrides.key ?? "id",
    entity_type: "person",
    key: "field",
    label_key: "custom.person.field",
    help_key: null,
    field_type: "text",
    required: false,
    options: [],
    min_value: null,
    max_value: null,
    max_length: null,
    pattern: null,
    visible_roles: [],
    active: true,
    order: 0,
    group_key: null,
    ...overrides,
  };
}

const DEFINITIONS: CustomFieldDefinition[] = [
  definition({ key: "blood_group", field_type: "select", options: ["A+", "O+"], label_key: "custom.person.blood_group" }),
  definition({ key: "siblings", field_type: "integer", label_key: "custom.person.siblings", min_value: "0" }),
  definition({ key: "boarding", field_type: "boolean", label_key: "custom.person.boarding" }),
  definition({ key: "arrival", field_type: "date", label_key: "custom.person.arrival" }),
  definition({ key: "clubs", field_type: "multiselect", options: ["chess", "music"], label_key: "custom.person.clubs" }),
  definition({ key: "code", field_type: "text", label_key: "custom.person.code", required: true }),
];

function renderForm(value: Record<string, unknown> = {}, extra: { errors?: Record<string, string>; onChange?: (next: Record<string, unknown>) => void } = {}) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <I18nProvider initialMessages={messages}>
        <CustomFieldsForm
          entityType="person"
          value={value}
          onChange={extra.onChange ?? (() => {})}
          errors={extra.errors}
        />
      </I18nProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.setItem("erp.access_token", "test-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify({ items: DEFINITIONS, next_cursor: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("CustomFieldsForm", () => {
  it("renders the configured fields with their own controls", async () => {
    renderForm();
    expect(await screen.findByLabelText(/Blood group/)).toBeInTheDocument();
    expect(screen.getByTestId("custom-field-blood_group")).toBeInTheDocument();
    expect(screen.getByTestId("custom-field-siblings")).toHaveAttribute("type", "number");
    expect(screen.getByTestId("custom-field-boarding")).toHaveAttribute("type", "checkbox");
    expect(screen.getByTestId("custom-field-clubs-chess")).toBeInTheDocument();
    expect(screen.getByTestId("custom-field-arrival-input")).toBeInTheDocument();
    expect(screen.getByText("Additional information")).toBeInTheDocument();
  });

  it("reports typed values for each kind of field", async () => {
    const onChange = vi.fn();
    renderForm({}, { onChange });
    await screen.findByTestId("custom-field-blood_group");

    fireEvent.change(screen.getByTestId("custom-field-blood_group"), {
      target: { value: "O+" },
    });
    expect(onChange).toHaveBeenLastCalledWith({ blood_group: "O+" });

    fireEvent.change(screen.getByTestId("custom-field-siblings"), { target: { value: "2" } });
    expect(onChange).toHaveBeenLastCalledWith({ siblings: "2" });

    fireEvent.click(screen.getByTestId("custom-field-boarding"));
    expect(onChange).toHaveBeenLastCalledWith({ boarding: true });

    fireEvent.click(screen.getByTestId("custom-field-clubs-music"));
    expect(onChange).toHaveBeenLastCalledWith({ clubs: ["music"] });
  });

  it("shows translated server errors next to the field and marks required fields", async () => {
    renderForm({}, { errors: { code: "error.custom_field.required" } });
    await screen.findByTestId("custom-field-code");
    expect(screen.getByTestId("custom-error-code")).toHaveTextContent("This field is required");
    expect(screen.getByText("*")).toBeInTheDocument();
    expect(screen.getAllByText("(Optional)").length).toBeGreaterThan(0);
  });

  it("states clearly when nothing is configured", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    renderForm();
    await waitFor(() =>
      expect(
        screen.getByText("No extra fields are configured for this record."),
      ).toBeInTheDocument(),
    );
  });
});
