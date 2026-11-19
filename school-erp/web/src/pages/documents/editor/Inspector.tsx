import type { Layout, LayoutElement, TextStyle } from "@erp/documents";
import { Button, Field, Input, Select, Textarea, Checkbox } from "@erp/ui-web";

import { useI18n } from "../../../providers/I18nProvider";
import { pageSizeMm } from "../types";

function NumberInput({
  label,
  value,
  onChange,
  step = 0.1,
  testId,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: number;
  testId?: string;
}) {
  return (
    <Field label={label}>
      <Input
        type="number"
        step={step}
        value={Number.isFinite(value) ? value : 0}
        data-testid={testId}
        onChange={(event) => {
          const next = Number(event.target.value);
          if (Number.isFinite(next)) onChange(next);
        }}
      />
    </Field>
  );
}

function ColourInput({
  label,
  value,
  onChange,
  testId,
}: {
  label: string;
  value: string | undefined;
  onChange: (value: string | undefined) => void;
  testId?: string;
}) {
  const { t } = useI18n();
  return (
    <div className="doc-colour">
      <Field label={label}>
        <div className="doc-colour__row">
          <Input
            type="color"
            value={value ?? "#ffffff"}
            onChange={(event) => onChange(event.target.value)}
            data-testid={testId}
          />
          <Input
            value={value ?? ""}
            placeholder="#000000"
            onChange={(event) => onChange(event.target.value || undefined)}
          />
          {value ? (
            <Button variant="ghost" size="sm" onClick={() => onChange(undefined)}>
              {t("documents.editor.background_none")}
            </Button>
          ) : null}
        </div>
      </Field>
    </div>
  );
}

function StyleFields({
  style,
  onChange,
}: {
  style: TextStyle;
  onChange: (patch: Partial<TextStyle>) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="doc-inspector__grid">
      <Field label={t("documents.editor.font_family")}>
        <Input
          value={style.font_family}
          onChange={(event) => onChange({ font_family: event.target.value })}
        />
      </Field>
      <NumberInput
        label={t("documents.editor.font_size")}
        value={style.font_size_pt}
        onChange={(value) => onChange({ font_size_pt: value })}
        step={0.5}
      />
      <NumberInput
        label={t("documents.editor.line_height")}
        value={style.line_height}
        onChange={(value) => onChange({ line_height: value })}
        step={0.1}
      />
      <NumberInput
        label={t("documents.editor.letter_spacing")}
        value={style.letter_spacing_pt}
        onChange={(value) => onChange({ letter_spacing_pt: value })}
        step={0.1}
      />
      <ColourInput
        label={t("documents.editor.colour")}
        value={style.colour}
        onChange={(value) => onChange({ colour: value ?? "#111111" })}
      />
      <div className="doc-inspector__checks">
        <Checkbox
          label={t("documents.editor.bold")}
          checked={style.bold}
          onChange={(event) => onChange({ bold: event.target.checked })}
        />
        <Checkbox
          label={t("documents.editor.italic")}
          checked={style.italic}
          onChange={(event) => onChange({ italic: event.target.checked })}
        />
        <Checkbox
          label={t("documents.editor.underline")}
          checked={style.underline}
          onChange={(event) => onChange({ underline: event.target.checked })}
        />
      </div>
    </div>
  );
}

export interface InspectorProps {
  layout: Layout;
  element: LayoutElement | null;
  onChange: (layout: Layout) => void;
}

type Visibility = NonNullable<LayoutElement["visible_when"]>;
type LeafVisibility = Extract<Visibility, { op: string }> & {
  value?: string | number | boolean;
};

function isLeafCondition(condition: Visibility): condition is LeafVisibility {
  return !("all" in condition) && !("any" in condition);
}

const COMPARISON_OPS = ["eq", "ne", "gt", "gte", "lt", "lte", "contains"] as const;

export function Inspector({ layout, element, onChange }: InspectorProps) {
  const { t } = useI18n();
  if (!element) {
    return (
      <section className="doc-panel" aria-label={t("documents.editor.inspector")} data-testid="inspector">
        <h2 className="doc-panel__title">{t("documents.editor.inspector")}</h2>
        <p className="ui-help">{t("documents.editor.no_selection")}</p>
      </section>
    );
  }

  const patch = (values: Partial<LayoutElement>) => {
    onChange({
      ...layout,
      elements: layout.elements.map((item) =>
        item.id === element.id ? ({ ...item, ...values } as LayoutElement) : item,
      ),
    });
  };
  const patchRect = (values: Partial<LayoutElement["rect"]>) => {
    onChange({
      ...layout,
      elements: layout.elements.map((item) =>
        item.id === element.id ? { ...item, rect: { ...item.rect, ...values } } : item,
      ),
    });
  };
  const page = pageSizeMm(layout.page);
  const margin = layout.page.margins_mm;
  const align = (horizontal: "left" | "center" | "right") => {
    const widths = element.rect.w_mm;
    const x =
      horizontal === "left"
        ? margin.left
        : horizontal === "center"
          ? (page.width - widths) / 2
          : page.width - margin.right - widths;
    patchRect({ x_mm: x });
  };

  return (
    <section className="doc-panel" aria-label={t("documents.editor.inspector")} data-testid="inspector">
      <h2 className="doc-panel__title">{t("documents.editor.inspector")}</h2>
      <div className="doc-inspector__actions">
        <Button variant="outline" size="sm" onClick={() => align("left")} aria-label={t("documents.editor.align_left")}>
          ⇤
        </Button>
        <Button variant="outline" size="sm" onClick={() => align("center")} aria-label={t("documents.editor.align_center")}>
          ⇔
        </Button>
        <Button variant="outline" size="sm" onClick={() => align("right")} aria-label={t("documents.editor.align_right")}>
          ⇥
        </Button>
        <Checkbox
          label={t("documents.editor.lock")}
          checked={element.locked}
          onChange={(event) => patch({ locked: event.target.checked })}
        />
      </div>

      <h3 className="doc-panel__subtitle">{t("documents.editor.position")}</h3>
      <div className="doc-inspector__grid">
        <NumberInput label={t("documents.editor.x")} value={element.rect.x_mm} onChange={(x_mm) => patchRect({ x_mm })} testId="inspector-x" />
        <NumberInput label={t("documents.editor.y")} value={element.rect.y_mm} onChange={(y_mm) => patchRect({ y_mm })} testId="inspector-y" />
        <NumberInput label={t("documents.editor.width")} value={element.rect.w_mm} onChange={(w_mm) => patchRect({ w_mm: Math.max(2, w_mm) })} />
        <NumberInput label={t("documents.editor.height")} value={element.rect.h_mm} onChange={(h_mm) => patchRect({ h_mm: Math.max(1, h_mm) })} />
        <NumberInput label={t("documents.editor.rotation")} value={element.rotation_deg} onChange={(rotation_deg) => patch({ rotation_deg })} step={1} />
        <NumberInput label={t("documents.editor.z")} value={element.z} onChange={(z) => patch({ z: Math.round(z) })} step={1} />
      </div>

      {element.type === "text" ? (
        <>
          <h3 className="doc-panel__subtitle">{t("documents.editor.content")}</h3>
          <Field label={t("documents.editor.text_content")}>
            <Textarea
              rows={4}
              value={element.content}
              data-testid="inspector-text"
              onChange={(event) => patch({ content: event.target.value })}
            />
          </Field>
          <div className="doc-inspector__grid">
            <Field label={t("documents.editor.align")}>
              <Select value={element.align} onChange={(event) => patch({ align: event.target.value as "left" | "center" | "right" })}>
                <option value="left">{t("documents.editor.align_left")}</option>
                <option value="center">{t("documents.editor.align_center")}</option>
                <option value="right">{t("documents.editor.align_right")}</option>
              </Select>
            </Field>
            <Field label={t("documents.editor.vertical_align")}>
              <Select value={element.vertical_align} onChange={(event) => patch({ vertical_align: event.target.value as "top" | "middle" | "bottom" })}>
                <option value="top">{t("documents.editor.top")}</option>
                <option value="middle">{t("documents.editor.middle")}</option>
                <option value="bottom">{t("documents.editor.bottom")}</option>
              </Select>
            </Field>
          </div>
          <Checkbox label={t("documents.editor.wrap")} checked={element.wrap} onChange={(event) => patch({ wrap: event.target.checked })} />
          <h3 className="doc-panel__subtitle">{t("documents.editor.style")}</h3>
          <StyleFields style={element.style} onChange={(values) => patch({ style: { ...element.style, ...values } })} />
          <h3 className="doc-panel__subtitle">{t("documents.editor.format")}</h3>
          <div className="doc-inspector__grid">
            <Field label={t("documents.editor.calendar")}>
              <Select
                value={element.format?.calendar ?? ""}
                onChange={(event) =>
                  patch({ format: { ...element.format, calendar: (event.target.value || undefined) as "ec" | "gc" | "both" | undefined } })
                }
              >
                <option value="">{t("documents.editor.calendar_none")}</option>
                <option value="ec">{t("documents.editor.calendar_ec")}</option>
                <option value="gc">{t("documents.editor.calendar_gc")}</option>
                <option value="both">{t("documents.editor.calendar_both")}</option>
              </Select>
            </Field>
            <Field label={t("documents.editor.script")}>
              <Select
                value={element.format?.script ?? ""}
                onChange={(event) =>
                  patch({ format: { ...element.format, script: (event.target.value || undefined) as "am" | "en" | undefined } })
                }
              >
                <option value="">{t("documents.editor.script_none")}</option>
                <option value="en">{t("documents.editor.script_en")}</option>
                <option value="am">{t("documents.editor.script_am")}</option>
              </Select>
            </Field>
          </div>
        </>
      ) : null}

      {element.type === "image" ? (
        <>
          <h3 className="doc-panel__subtitle">{t("documents.editor.image_source")}</h3>
          <div className="doc-inspector__grid">
            <Field label={t("documents.editor.source_field")}>
              <Select
                value={element.source.kind}
                onChange={(event) => patch({ source: { ...element.source, kind: event.target.value as "field" | "file" | "url" } })}
              >
                <option value="field">{t("documents.editor.source_field")}</option>
                <option value="file">{t("documents.editor.source_file")}</option>
                <option value="url">{t("documents.editor.source_url")}</option>
              </Select>
            </Field>
            <Field label={t("documents.editor.source_value")}>
              <Input value={element.source.value} onChange={(event) => patch({ source: { ...element.source, value: event.target.value } })} />
            </Field>
            <Field label={t("documents.editor.fit")}>
              <Select value={element.fit} onChange={(event) => patch({ fit: event.target.value as "contain" | "cover" | "fill" })}>
                <option value="contain">{t("documents.editor.fit_contain")}</option>
                <option value="cover">{t("documents.editor.fit_cover")}</option>
                <option value="fill">{t("documents.editor.fit_fill")}</option>
              </Select>
            </Field>
          </div>
          <Field label={t("documents.editor.alt")}>
            <Input value={element.alt ?? ""} onChange={(event) => patch({ alt: event.target.value || undefined })} />
          </Field>
        </>
      ) : null}

      {element.type === "shape" ? (
        <>
          <h3 className="doc-panel__subtitle">{t("documents.editor.shape_kind")}</h3>
          <div className="doc-inspector__grid">
            <Field label={t("documents.editor.shape_kind")}>
              <Select value={element.shape} onChange={(event) => patch({ shape: event.target.value as "rect" | "ellipse" | "line" })}>
                <option value="rect">{t("documents.editor.shape_rect")}</option>
                <option value="ellipse">{t("documents.editor.shape_ellipse")}</option>
                <option value="line">{t("documents.editor.shape_line")}</option>
              </Select>
            </Field>
            <ColourInput label={t("documents.editor.fill")} value={element.fill} onChange={(fill) => patch({ fill })} />
            <ColourInput
              label={t("documents.editor.stroke")}
              value={element.stroke?.colour}
              onChange={(colour) =>
                patch({ stroke: colour ? { colour, width_mm: element.stroke?.width_mm ?? 0.4 } : undefined })
              }
            />
            <NumberInput
              label={t("documents.editor.stroke_width")}
              value={element.stroke?.width_mm ?? 0}
              onChange={(width_mm) => patch({ stroke: { colour: element.stroke?.colour ?? "#334155", width_mm } })}
            />
            <NumberInput label={t("documents.editor.radius")} value={element.radius_mm} onChange={(radius_mm) => patch({ radius_mm })} />
          </div>
        </>
      ) : null}

      {element.type === "table" ? (
        <>
          <h3 className="doc-panel__subtitle">{t("documents.editor.table_columns")}</h3>
          <Field label={t("documents.editor.table_source")}>
            <Input value={element.table.source} onChange={(event) => patch({ table: { ...element.table, source: event.target.value } })} />
          </Field>
          <div className="doc-inspector__grid">
            <NumberInput
              label={t("documents.editor.row_height")}
              value={element.table.row_height_mm}
              onChange={(row_height_mm) => patch({ table: { ...element.table, row_height_mm } })}
            />
            <Checkbox
              label={t("documents.editor.show_header")}
              checked={element.table.show_header}
              onChange={(event) => patch({ table: { ...element.table, show_header: event.target.checked } })}
            />
            <Checkbox
              label={t("documents.editor.repeat_header")}
              checked={element.table.repeat_header}
              onChange={(event) => patch({ table: { ...element.table, repeat_header: event.target.checked } })}
            />
          </div>
          <div className="doc-columns">
            {element.table.columns.map((column, index) => {
              const computed = column.computed;
              const others = element.table.columns.filter(
                (item) => item.key !== column.key && item.computed === undefined,
              );
              return (
                <div className="doc-column" key={`${column.key}-${index}`}>
                  <Input
                    value={column.label}
                    aria-label={t("documents.editor.column_label")}
                    onChange={(event) => {
                      const columns = element.table.columns.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, label: event.target.value } : item,
                      );
                      patch({ table: { ...element.table, columns } });
                    }}
                  />
                  <Input
                    value={column.group ?? ""}
                    aria-label={t("documents.editor.column_group")}
                    placeholder={t("documents.editor.column_group")}
                    onChange={(event) => {
                      const columns = element.table.columns.map((item, itemIndex) =>
                        itemIndex === index
                          ? { ...item, group: event.target.value || undefined }
                          : item,
                      );
                      patch({ table: { ...element.table, columns } });
                    }}
                  />
                  <Select
                    value={computed?.op ?? "none"}
                    aria-label={t("documents.editor.column_computed")}
                    onChange={(event) => {
                      const op = event.target.value;
                      const columns = element.table.columns.map((item, itemIndex) => {
                        if (itemIndex !== index) return item;
                        if (op === "none") return { ...item, computed: undefined };
                        if (op === "rank") {
                          return {
                            ...item,
                            binding: undefined,
                            computed: {
                              op: "rank" as const,
                              by: others[0]?.key ?? item.key,
                              descending: true,
                            },
                          };
                        }
                        return {
                          ...item,
                          binding: undefined,
                          computed: {
                            op: op as "sum" | "average",
                            of: others.slice(0, 1).map((other) => other.key),
                          },
                        };
                      });
                      patch({ table: { ...element.table, columns } });
                    }}
                  >
                    <option value="none">{t("documents.editor.computed_none")}</option>
                    <option value="sum" disabled={others.length === 0}>
                      {t("documents.editor.computed_sum")}
                    </option>
                    <option value="average" disabled={others.length === 0}>
                      {t("documents.editor.computed_average")}
                    </option>
                    <option value="rank" disabled={others.length === 0}>
                      {t("documents.editor.computed_rank")}
                    </option>
                  </Select>
                  {computed === undefined ? (
                    <Input
                      value={column.binding ?? ""}
                      aria-label={t("documents.editor.column_binding")}
                      placeholder={t("documents.editor.column_binding")}
                      onChange={(event) => {
                        const columns = element.table.columns.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, binding: event.target.value || undefined }
                            : item,
                        );
                        patch({ table: { ...element.table, columns } });
                      }}
                    />
                  ) : computed.op === "rank" ? (
                    <>
                      <Input
                        value={computed.by}
                        aria-label={t("documents.editor.computed_by")}
                        placeholder={t("documents.editor.computed_by")}
                        onChange={(event) => {
                          const columns = element.table.columns.map((item, itemIndex) =>
                            itemIndex === index
                              ? {
                                  ...item,
                                  computed: {
                                    op: "rank" as const,
                                    by: event.target.value,
                                    descending: computed.descending,
                                  },
                                }
                              : item,
                          );
                          patch({ table: { ...element.table, columns } });
                        }}
                      />
                      <Checkbox
                        label={t("documents.editor.computed_descending")}
                        checked={computed.descending}
                        onChange={(event) => {
                          const columns = element.table.columns.map((item, itemIndex) =>
                            itemIndex === index
                              ? {
                                  ...item,
                                  computed: {
                                    op: "rank" as const,
                                    by: computed.by,
                                    descending: event.target.checked,
                                  },
                                }
                              : item,
                          );
                          patch({ table: { ...element.table, columns } });
                        }}
                      />
                    </>
                  ) : (
                    <Input
                      value={computed.of.join(", ")}
                      aria-label={t("documents.editor.computed_of")}
                      placeholder={t("documents.editor.computed_of")}
                      onChange={(event) => {
                        const of = event.target.value
                          .split(",")
                          .map((value) => value.trim())
                          .filter(Boolean);
                        const columns = element.table.columns.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, computed: { op: computed.op, of } }
                            : item,
                        );
                        patch({ table: { ...element.table, columns } });
                      }}
                    />
                  )}
                  <Select
                    value={column.align}
                    aria-label={t("documents.editor.align")}
                    onChange={(event) => {
                      const columns = element.table.columns.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, align: event.target.value as "left" | "center" | "right" } : item,
                      );
                      patch({ table: { ...element.table, columns } });
                    }}
                  >
                    <option value="left">{t("documents.editor.align_left")}</option>
                    <option value="center">{t("documents.editor.align_center")}</option>
                    <option value="right">{t("documents.editor.align_right")}</option>
                  </Select>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t("documents.editor.column_remove")}
                    disabled={element.table.columns.length <= 1}
                    onClick={() =>
                      patch({
                        table: {
                          ...element.table,
                          columns: element.table.columns
                            .filter((_, itemIndex) => itemIndex !== index)
                            .map((item) => {
                              if (item.computed === undefined) return item;
                              if (item.computed.op === "rank") {
                                return item.computed.by === column.key
                                  ? { ...item, computed: undefined }
                                  : item;
                              }
                              const of = item.computed.of.filter(
                                (reference) => reference !== column.key,
                              );
                              return of.length
                                ? { ...item, computed: { ...item.computed, of } }
                                : { ...item, computed: undefined };
                            }),
                          summaries: element.table.summaries.filter(
                            (summary) => summary.column !== column.key,
                          ),
                        },
                      })
                    }
                  >
                    ×
                  </Button>
                </div>
              );
            })}
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                patch({
                  table: {
                    ...element.table,
                    columns: [
                      ...element.table.columns,
                      {
                        key: `column_${element.table.columns.length + 1}`,
                        label: "Column",
                        align: "left",
                      },
                    ],
                  },
                })
              }
            >
              {t("documents.editor.column_add")}
            </Button>
          </div>
          <div className="doc-inspector__row">
            <h3 className="doc-panel__subtitle">{t("documents.editor.summaries")}</h3>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                patch({
                  table: {
                    ...element.table,
                    summaries: [
                      ...element.table.summaries,
                      {
                        column: element.table.columns[0].key,
                        aggregate: "sum",
                        label: t("documents.editor.summary_sum"),
                      },
                    ],
                  },
                })
              }
            >
              {t("documents.editor.summary_add")}
            </Button>
          </div>
          {element.table.summaries.map((summary, index) => (
            <div className="doc-column" key={`${summary.column}-${summary.aggregate}-${index}`}>
              <Select
                value={summary.column}
                aria-label={t("documents.editor.summary_column")}
                onChange={(event) => {
                  const summaries = element.table.summaries.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, column: event.target.value } : item,
                  );
                  patch({ table: { ...element.table, summaries } });
                }}
              >
                {element.table.columns.map((column) => (
                  <option key={column.key} value={column.key}>
                    {column.label}
                  </option>
                ))}
              </Select>
              <Select
                value={summary.aggregate}
                aria-label={t("documents.editor.summary_aggregate")}
                onChange={(event) => {
                  const summaries = element.table.summaries.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, aggregate: event.target.value as "sum" | "average" | "count" }
                      : item,
                  );
                  patch({ table: { ...element.table, summaries } });
                }}
              >
                <option value="sum">{t("documents.editor.summary_sum")}</option>
                <option value="average">{t("documents.editor.summary_average")}</option>
                <option value="count">{t("documents.editor.summary_count")}</option>
              </Select>
              <Input
                value={summary.label}
                aria-label={t("documents.editor.summary_label")}
                onChange={(event) => {
                  const summaries = element.table.summaries.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, label: event.target.value } : item,
                  );
                  patch({ table: { ...element.table, summaries } });
                }}
              />
              <Button
                variant="ghost"
                size="sm"
                aria-label={t("documents.editor.summary_remove")}
                onClick={() =>
                  patch({
                    table: {
                      ...element.table,
                      summaries: element.table.summaries.filter(
                        (_, itemIndex) => itemIndex !== index,
                      ),
                    },
                  })
                }
              >
                ×
              </Button>
            </div>
          ))}
          <h3 className="doc-panel__subtitle">{t("documents.editor.style")}</h3>
          <StyleFields style={element.style} onChange={(values) => patch({ style: { ...element.style, ...values } })} />
        </>
      ) : null}

      {element.type === "qr" ? (
        <>
          <h3 className="doc-panel__subtitle">{t("documents.editor.qr_data")}</h3>
          <div className="doc-inspector__grid">
            <Field label={t("documents.editor.qr_data")}>
              <Input value={element.data} onChange={(event) => patch({ data: event.target.value })} />
            </Field>
            <Field label={t("documents.editor.qr_error")}>
              <Select
                value={element.error_correction}
                onChange={(event) => patch({ error_correction: event.target.value as "L" | "M" | "Q" | "H" })}
              >
                {["L", "M", "Q", "H"].map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </Select>
            </Field>
            <ColourInput label={t("documents.editor.foreground")} value={element.foreground} onChange={(foreground) => patch({ foreground: foreground ?? "#000000" })} />
            <ColourInput label={t("documents.editor.barcode_background")} value={element.background} onChange={(background) => patch({ background: background ?? "#ffffff" })} />
          </div>
        </>
      ) : null}

      {element.type === "barcode" ? (
        <>
          <h3 className="doc-panel__subtitle">{t("documents.editor.add_barcode")}</h3>
          <div className="doc-inspector__grid">
            <Field label={t("documents.editor.qr_data")}>
              <Input value={element.data} onChange={(event) => patch({ data: event.target.value })} />
            </Field>
            <Field label={t("documents.editor.barcode_symbology")}>
              <Select
                value={element.symbology}
                onChange={(event) => patch({ symbology: event.target.value as "code128" | "code39" | "ean13" | "ean8" })}
              >
                {["code128", "code39", "ean13", "ean8"].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Select>
            </Field>
            <ColourInput label={t("documents.editor.foreground")} value={element.foreground} onChange={(foreground) => patch({ foreground: foreground ?? "#000000" })} />
            <ColourInput label={t("documents.editor.barcode_background")} value={element.background} onChange={(background) => patch({ background: background ?? "#ffffff" })} />
          </div>
          <Checkbox
            label={t("documents.editor.barcode_show_text")}
            checked={element.show_text}
            onChange={(event) => patch({ show_text: event.target.checked })}
          />
        </>
      ) : null}

      <h3 className="doc-panel__subtitle">{t("documents.editor.condition")}</h3>
      {element.visible_when === undefined ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => patch({ visible_when: { op: "exists", field: "" } })}
        >
          {t("documents.editor.condition_exists")}
        </Button>
      ) : isLeafCondition(element.visible_when) ? (
        <div className="doc-inspector__grid">
          <Field label={t("documents.editor.condition_field")}>
            <Input
              value={element.visible_when.field}
              onChange={(event) =>
                patch({
                  visible_when: { ...(element.visible_when as LeafVisibility), field: event.target.value },
                })
              }
            />
          </Field>
          <Field label={t("documents.editor.condition_operator")}>
            <Select
              value={element.visible_when.op}
              onChange={(event) => {
                const op = event.target.value;
                if (op === "exists" || op === "empty") {
                  patch({
                    visible_when: {
                      op,
                      field: (element.visible_when as LeafVisibility).field,
                    } as Visibility,
                  });
                } else {
                  patch({
                    visible_when: {
                      op: op as (typeof COMPARISON_OPS)[number],
                      field: (element.visible_when as LeafVisibility).field,
                      value: (element.visible_when as LeafVisibility).value ?? "",
                    } as Visibility,
                  });
                }
              }}
            >
              <option value="exists">{t("documents.editor.condition_exists")}</option>
              <option value="empty">{t("documents.editor.condition_empty")}</option>
              {COMPARISON_OPS.map((op) => (
                <option key={op} value={op}>
                  {t(`documents.editor.condition_${op}`)}
                </option>
              ))}
            </Select>
          </Field>
          {element.visible_when.op !== "exists" && element.visible_when.op !== "empty" ? (
            <Field label={t("documents.editor.condition_value")}>
              <Input
                value={String(element.visible_when.value ?? "")}
                onChange={(event) =>
                  patch({
                    visible_when: {
                      ...(element.visible_when as LeafVisibility),
                      value: event.target.value,
                    } as Visibility,
                  })
                }
              />
            </Field>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => patch({ visible_when: undefined })}
          >
            {t("documents.editor.condition_clear")}
          </Button>
        </div>
      ) : (
        <div className="doc-inspector__actions">
          <span>{t("documents.editor.condition_complex")}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => patch({ visible_when: undefined })}
          >
            {t("documents.editor.condition_clear")}
          </Button>
        </div>
      )}
    </section>
  );
}
