import { useQuery } from "@tanstack/react-query";
import { useMemo, type ReactNode } from "react";

import { CalendarDatePicker } from "./CalendarDatePicker";
import { Input } from "./ui/Input";
import { api } from "../lib/api";
import { useI18n } from "../providers/I18nProvider";

export interface CustomFieldDefinition {
  id: string;
  entity_type: string;
  key: string;
  label_key: string;
  help_key: string | null;
  field_type:
    | "text"
    | "long_text"
    | "integer"
    | "number"
    | "boolean"
    | "date"
    | "select"
    | "multiselect";
  required: boolean;
  options: string[];
  min_value: string | null;
  max_value: string | null;
  max_length: number | null;
  pattern: string | null;
  visible_roles: string[];
  active: boolean;
  order: number;
  group_key: string | null;
}

type Values = Record<string, unknown>;

/**
 * Renders the definitions configured for an entity. Values are opaque to this
 * component; the server validates them with the same definitions (P1-17), so
 * errors arrive as i18n keys and are translated here.
 */
export function CustomFieldsForm({
  entityType,
  definitions: provided,
  value,
  onChange,
  errors = {},
  disabled = false,
}: {
  entityType: string;
  /** Definitions from a public endpoint; skips the authenticated fetch when set. */
  definitions?: CustomFieldDefinition[];
  value: Values;
  onChange: (value: Values) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const query = useQuery({
    queryKey: ["custom-fields", entityType],
    queryFn: () =>
      api.get<{ items: CustomFieldDefinition[] }>(
        `/api/v1/custom-fields?entity_type=${encodeURIComponent(entityType)}`,
      ),
    enabled: provided === undefined,
  });

  const definitions = useMemo(
    () => (provided ?? query.data?.items ?? []).filter((definition) => definition.active),
    [provided, query.data],
  );

  const set = (key: string, next: unknown) => onChange({ ...value, [key]: next });

  if (provided === undefined && query.isLoading) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        {t("custom.loading")}
      </p>
    );
  }

  if (provided === undefined && query.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {t("common.error")}
      </p>
    );
  }

  if (definitions.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("custom.empty")}</p>;
  }

  const renderField = (definition: CustomFieldDefinition) => {
    const label = t(definition.label_key);
    const errorKey = errors[definition.key];
    const error = errorKey ? t(errorKey) : null;
    const common = {
      "data-testid": `custom-field-${definition.key}`,
      disabled,
    } as const;
    const help = definition.help_key ? (
      <p className="text-xs text-muted-foreground">{t(definition.help_key)}</p>
    ) : null;

    let control: ReactNode;
    switch (definition.field_type) {
      case "long_text":
        control = (
          <textarea
            {...common}
            className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            maxLength={definition.max_length ?? undefined}
            value={String(value[definition.key] ?? "")}
            onChange={(event) => set(definition.key, event.target.value)}
          />
        );
        break;
      case "integer":
      case "number":
        control = (
          <Input
            {...common}
            type="number"
            min={definition.min_value ?? undefined}
            max={definition.max_value ?? undefined}
            step={definition.field_type === "integer" ? 1 : "any"}
            value={String(value[definition.key] ?? "")}
            onChange={(event) => set(definition.key, event.target.value)}
          />
        );
        break;
      case "boolean":
        control = (
          <input
            {...common}
            type="checkbox"
            className="h-4 w-4 rounded border-input"
            checked={value[definition.key] === true}
            onChange={(event) => set(definition.key, event.target.checked)}
          />
        );
        break;
      case "date":
        control = (
          <CalendarDatePicker
            testId={`custom-field-${definition.key}`}
            value={String(value[definition.key] ?? "")}
            onChange={(isoDate) => set(definition.key, isoDate)}
          />
        );
        break;
      case "select":
        control = (
          <select
            {...common}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            value={String(value[definition.key] ?? "")}
            onChange={(event) => set(definition.key, event.target.value)}
          >
            <option value="">{t("custom.choose")}</option>
            {definition.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        );
        break;
      case "multiselect": {
        const chosen = Array.isArray(value[definition.key])
          ? (value[definition.key] as string[])
          : [];
        control = (
          <div role="group" aria-label={label} data-testid={`custom-field-${definition.key}`}>
            <p className="text-xs text-muted-foreground">{t("custom.multiselect.hint")}</p>
            {definition.options.map((option) => (
              <label key={option} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  data-testid={`custom-field-${definition.key}-${option}`}
                  disabled={disabled}
                  checked={chosen.includes(option)}
                  onChange={(event) =>
                    set(
                      definition.key,
                      event.target.checked
                        ? [...chosen, option]
                        : chosen.filter((item) => item !== option),
                    )
                  }
                />
                {option}
              </label>
            ))}
          </div>
        );
        break;
      }
      default:
        control = (
          <Input
            {...common}
            maxLength={definition.max_length ?? undefined}
            pattern={definition.pattern ?? undefined}
            value={String(value[definition.key] ?? "")}
            onChange={(event) => set(definition.key, event.target.value)}
          />
        );
    }

    return (
      <div key={definition.id} className="space-y-1" data-group={definition.group_key ?? ""}>
        <label className="block text-sm">
          <span className="text-muted-foreground">
            {label}
            {definition.required ? (
              <span className="ml-1 text-destructive" aria-hidden="true">
                *
              </span>
            ) : (
              <span className="ml-1 text-xs">({t("custom.optional")})</span>
            )}
          </span>
          {control}
        </label>
        {help}
        {error ? (
          <p role="alert" className="text-sm text-destructive" data-testid={`custom-error-${definition.key}`}>
            {error}
          </p>
        ) : null}
      </div>
    );
  };

  return (
    <fieldset className="space-y-4" data-testid="custom-fields-form">
      <legend className="text-sm font-semibold">{t("custom.title")}</legend>
      {definitions.map(renderField)}
    </fieldset>
  );
}
