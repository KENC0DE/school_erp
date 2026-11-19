import type { Layout, LayoutElement } from "@erp/documents";
import { Button } from "@erp/ui-web";

import { useI18n } from "../../../providers/I18nProvider";
import type { FieldDefinition } from "../types";
import { elementDescription } from "./ElementView";

const ICONS: Record<LayoutElement["type"], string> = {
  text: "T",
  image: "▣",
  shape: "◻",
  table: "▦",
  qr: "▩",
  barcode: "|||",
};

export function LayersPanel({
  layout,
  selectedId,
  fields,
  readOnly,
  onSelect,
  onChange,
}: {
  layout: Layout;
  selectedId: string | null;
  fields: Map<string, FieldDefinition>;
  readOnly: boolean;
  onSelect: (id: string) => void;
  onChange: (layout: Layout) => void;
}) {
  const { t } = useI18n();
  const ordered = [...layout.elements].sort((a, b) => b.z - a.z);

  const reorder = (element: LayoutElement, direction: -1 | 1) => {
    const ascending = [...layout.elements].sort((a, b) => a.z - b.z);
    const index = ascending.findIndex((item) => item.id === element.id);
    const target = index + direction;
    if (target < 0 || target >= ascending.length) return;
    const next = [...ascending];
    [next[index], next[target]] = [next[target], next[index]];
    onChange({
      ...layout,
      elements: next.map((item, order) => ({ ...item, z: order + 1 })),
    });
  };

  return (
    <section className="doc-panel" aria-label={t("documents.editor.layers")} data-testid="layers-panel">
      <h2 className="doc-panel__title">{t("documents.editor.layers")}</h2>
      {ordered.length === 0 ? (
        <p className="ui-help">{t("documents.editor.layers_empty")}</p>
      ) : (
        <ul className="doc-layers">
          {ordered.map((element) => (
            <li
              key={element.id}
              className={`doc-layer${selectedId === element.id ? " doc-layer--selected" : ""}`}
              data-testid={`layer-${element.id}`}
            >
              <Button
                variant="ghost"
                size="sm"
                className="doc-layer__select"
                aria-label={elementDescription(element, fields)}
                onClick={() => onSelect(element.id)}
              >
                <span className="doc-layer__icon" aria-hidden="true">
                  {ICONS[element.type]}
                </span>
                <span className="doc-layer__text">{elementDescription(element, fields)}</span>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                iconOnly
                aria-label={element.locked ? t("documents.editor.unlock") : t("documents.editor.lock")}
                disabled={readOnly}
                onClick={() =>
                  onChange({
                    ...layout,
                    elements: layout.elements.map((item) =>
                      item.id === element.id ? { ...item, locked: !item.locked } : item,
                    ),
                  })
                }
              >
                {element.locked ? "🔒" : "🔓"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                iconOnly
                aria-label={t("documents.editor.bring_forward")}
                disabled={readOnly}
                onClick={() => reorder(element, 1)}
              >
                ↑
              </Button>
              <Button
                variant="ghost"
                size="sm"
                iconOnly
                aria-label={t("documents.editor.send_backward")}
                disabled={readOnly}
                onClick={() => reorder(element, -1)}
              >
                ↓
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
