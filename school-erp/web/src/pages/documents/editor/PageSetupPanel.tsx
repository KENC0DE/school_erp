import type { Layout } from "@erp/documents";
import { Button, Field, Input, Select } from "@erp/ui-web";

import { useI18n } from "../../../providers/I18nProvider";

export function PageSetupPanel({
  layout,
  readOnly,
  onChange,
}: {
  layout: Layout;
  readOnly: boolean;
  onChange: (layout: Layout) => void;
}) {
  const { t } = useI18n();
  const page = layout.page;
  const setPage = (patch: Partial<Layout["page"]>) =>
    onChange({ ...layout, page: { ...page, ...patch } });

  const changeSize = (size: Layout["page"]["size"]) => {
    if (size === "custom") {
      setPage({ size, width_mm: 210, height_mm: 297 });
      return;
    }
    const rest = { ...page };
    delete rest.width_mm;
    delete rest.height_mm;
    onChange({ ...layout, page: { ...rest, size } });
  };

  return (
    <section className="doc-panel" aria-label={t("documents.editor.page")} data-testid="page-setup">
      <h2 className="doc-panel__title">{t("documents.editor.page")}</h2>
      <div className="doc-inspector__grid">
        <Field label={t("documents.editor.page_size")}>
          <Select
            value={page.size}
            disabled={readOnly}
            data-testid="page-size"
            onChange={(event) => changeSize(event.target.value as Layout["page"]["size"])}
          >
            <option value="A4">{t("documents.editor.page_a4")}</option>
            <option value="A5">{t("documents.editor.page_a5")}</option>
            <option value="Letter">{t("documents.editor.page_letter")}</option>
            <option value="custom">{t("documents.editor.page_custom")}</option>
          </Select>
        </Field>
        <Field label={t("documents.editor.orientation")}>
          <Select
            value={page.orientation}
            disabled={readOnly}
            onChange={(event) => setPage({ orientation: event.target.value as "portrait" | "landscape" })}
          >
            <option value="portrait">{t("documents.editor.portrait")}</option>
            <option value="landscape">{t("documents.editor.landscape")}</option>
          </Select>
        </Field>
        {page.size === "custom" ? (
          <>
            <Field label={t("documents.editor.width")}>
              <Input
                type="number"
                min={10}
                max={5000}
                value={page.width_mm ?? 210}
                disabled={readOnly}
                onChange={(event) => setPage({ width_mm: Number(event.target.value) })}
              />
            </Field>
            <Field label={t("documents.editor.height")}>
              <Input
                type="number"
                min={10}
                max={5000}
                value={page.height_mm ?? 297}
                disabled={readOnly}
                onChange={(event) => setPage({ height_mm: Number(event.target.value) })}
              />
            </Field>
          </>
        ) : null}
        <Field label={t("documents.editor.bleed")}>
          <Input
            type="number"
            min={0}
            max={20}
            step={0.5}
            value={page.bleed_mm}
            disabled={readOnly}
            onChange={(event) => setPage({ bleed_mm: Number(event.target.value) })}
          />
        </Field>
      </div>

      <h3 className="doc-panel__subtitle">{t("documents.editor.margins")}</h3>
      <div className="doc-inspector__grid">
        {(
          [
            ["top", "documents.editor.margin_top"],
            ["right", "documents.editor.margin_right"],
            ["bottom", "documents.editor.margin_bottom"],
            ["left", "documents.editor.margin_left"],
          ] as const
        ).map(([side, key]) => (
          <Field label={t(key)} key={side}>
            <Input
              type="number"
              min={0}
              max={100}
              value={page.margins_mm[side]}
              disabled={readOnly}
              onChange={(event) =>
                setPage({
                  margins_mm: { ...page.margins_mm, [side]: Number(event.target.value) },
                })
              }
            />
          </Field>
        ))}
      </div>

      <h3 className="doc-panel__subtitle">{t("documents.editor.background")}</h3>
      <div className="doc-colour__row">
        <Input
          type="color"
          value={page.background_colour ?? "#ffffff"}
          disabled={readOnly}
          aria-label={t("documents.editor.background")}
          onChange={(event) => setPage({ background_colour: event.target.value })}
        />
        {page.background_colour ? (
          <Button variant="ghost" size="sm" disabled={readOnly} onClick={() => setPage({ background_colour: undefined })}>
            {t("documents.editor.background_none")}
          </Button>
        ) : null}
      </div>
    </section>
  );
}
