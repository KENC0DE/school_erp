import { Badge, Button, EmptyState, Input } from "@erp/ui-web";
import { useMemo, useState } from "react";

import { useI18n } from "../../../providers/I18nProvider";
import type { FieldDefinition } from "../types";

export function FieldPalette({
  fields,
  onPick,
}: {
  fields: FieldDefinition[];
  onPick: (field: FieldDefinition) => void;
}) {
  const { t } = useFieldTranslator();
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matched = fields.filter((field) => {
      if (!needle) return true;
      return (
        field.key.toLowerCase().includes(needle) ||
        t(field.label_key).toLowerCase().includes(needle)
      );
    });
    const grouped = new Map<string, FieldDefinition[]>();
    for (const field of matched) {
      const list = grouped.get(field.module) ?? [];
      list.push(field);
      grouped.set(field.module, list);
    }
    return [...grouped.entries()];
  }, [fields, query, t]);

  return (
    <section className="doc-panel" aria-label={t("documents.editor.fields")} data-testid="field-palette">
      <h2 className="doc-panel__title">{t("documents.editor.fields")}</h2>
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={t("documents.editor.fields_search")}
        aria-label={t("documents.editor.fields_search")}
        data-testid="field-search"
      />
      <p className="ui-help">{t("documents.editor.fields_hint")}</p>
      {groups.length === 0 ? (
        <EmptyState title={t("documents.editor.fields_empty")} />
      ) : (
        <div className="doc-field-groups">
          {groups.map(([module, items]) => (
            <div key={module}>
              <p className="doc-field-group__title">
                <Badge>{module}</Badge>
              </p>
              <ul className="doc-field-list">
                {items.map((field) => (
                  <li key={field.key}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="doc-field-button"
                      data-testid={`field-${field.key}`}
                      onClick={() => onPick(field)}
                      title={field.key}
                    >
                      <span>{t(field.label_key)}</span>
                      <code>{field.key}</code>
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** Small indirection so tests can provide the app translator without a hook. */
function useFieldTranslator(): { t: (key: string) => string } {
  return useI18n();
}
