import type { LayoutElement, TextElement } from "@erp/documents";
import { computeTableValues, summarizeColumn } from "@erp/documents/table";
import type { CSSProperties } from "react";

import type { FieldDefinition } from "../types";
import { resolveSample, sampleFor } from "./elements";

export const MM_TO_PX = 96 / 25.4;

const PLACEHOLDERS: Record<string, string> = {
  "school.logo": "editor.placeholder_logo",
  "student.signature": "editor.placeholder_signature",
  "school.stamp": "editor.placeholder_stamp",
  "student.photo": "editor.placeholder_photo",
};

function textStyle(element: TextElement, resolved: string): CSSProperties {
  return {
    fontFamily: `'${element.style.font_family}', 'Noto Sans Ethiopic', sans-serif`,
    fontSize: `${element.style.font_size_pt}pt`,
    fontWeight: element.style.bold ? 700 : 400,
    fontStyle: element.style.italic ? "italic" : "normal",
    textDecoration: element.style.underline ? "underline" : "none",
    color: element.style.colour,
    lineHeight: element.style.line_height,
    letterSpacing: `${element.style.letter_spacing_pt}pt`,
    textAlign: element.align,
    whiteSpace: element.wrap ? "pre-wrap" : "nowrap",
    overflow: "hidden",
    width: "100%",
    height: "100%",
    display: "flex",
    flexDirection: "column",
    justifyContent:
      element.vertical_align === "middle"
        ? "center"
        : element.vertical_align === "bottom"
          ? "flex-end"
          : "flex-start",
    wordBreak: "break-word",
    unicodeBidi: "plaintext",
    ["--resolved" as string]: resolved,
  };
}

function ImageView({ element, t }: { element: Extract<LayoutElement, { type: "image" }>; t: (key: string) => string }) {
  const source = element.source;
  if (source.value && (source.kind === "url" || source.kind === "file") && /^https?:|^data:image/.test(source.value)) {
    return (
      <img
        src={source.value}
        alt={element.alt ?? ""}
        style={{ width: "100%", height: "100%", objectFit: element.fit }}
        draggable={false}
      />
    );
  }
  const labelKey = PLACEHOLDERS[source.value] ?? element.alt;
  return (
    <div className="doc-placeholder" aria-hidden="true">
      <span>{labelKey ? t(labelKey) : source.value || t("documents.editor.add_image")}</span>
      {source.value ? <code>{source.value}</code> : null}
    </div>
  );
}

function TableView({
  element,
  fields,
}: {
  element: Extract<LayoutElement, { type: "table" }>;
  fields: Map<string, FieldDefinition>;
}) {
  const field = fields.get(element.table.source);
  const sampleRows = Array.isArray(field?.sample)
    ? (field.sample as Array<Record<string, unknown>>).slice(0, 6)
    : [];
  const rows = sampleRows.length
    ? sampleRows
    : Array.from({ length: 3 }, () =>
        Object.fromEntries(element.table.columns.map((column) => [column.key, "—"])),
      );
  const values = computeTableValues(rows, element.table.columns);
  const totalWidth = element.table.columns.reduce(
    (sum, column) => sum + (column.width_mm ?? 30),
    0,
  );
  const groups: Array<{ label: string | undefined; span: number }> = [];
  for (const column of element.table.columns) {
    const last = groups[groups.length - 1];
    if (last && last.label === column.group) last.span += 1;
    else groups.push({ label: column.group, span: 1 });
  }
  return (
    <table className="doc-table" style={{ fontSize: `${element.style.font_size_pt}pt`, fontFamily: `'${element.style.font_family}', sans-serif` }}>
      {element.table.show_header ? (
        <thead>
          {groups.some((group) => group.label) ? (
            <tr>
              {groups.map((group, index) => (
                <th key={index} colSpan={group.span} style={{ textAlign: "center" }}>
                  {group.label ?? ""}
                </th>
              ))}
            </tr>
          ) : null}
          <tr>
            {element.table.columns.map((column) => (
              <th
                key={column.key}
                style={{
                  width: `${((column.width_mm ?? 30) / totalWidth) * 100}%`,
                  textAlign: column.align,
                  color: element.style.colour,
                }}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
      ) : null}
      <tbody>
        {values.map((row, index) => (
          <tr key={index}>
            {element.table.columns.map((column) => (
              <td
                key={column.key}
                style={{ textAlign: column.align, color: element.style.colour }}
              >
                {row[column.key] || "—"}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
      {element.table.summaries.length ? (
        <tfoot>
          {element.table.summaries.map((summary) => (
            <tr key={`${summary.column}-${summary.aggregate}`}>
              {element.table.columns.map((column, index) =>
                index === 0 ? (
                  <td key={column.key} style={{ textAlign: column.align, color: element.style.colour }}>
                    {summary.label}
                  </td>
                ) : (
                  <td key={column.key} style={{ textAlign: column.align, color: element.style.colour }}>
                    {column.key === summary.column
                      ? summarizeColumn(
                          values,
                          column.key,
                          summary.aggregate,
                          column.format?.number_decimals,
                        )
                      : ""}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tfoot>
      ) : null}
    </table>
  );
}

export function ElementView({
  element,
  fields,
  t,
}: {
  element: LayoutElement;
  fields: Map<string, FieldDefinition>;
  t: (key: string) => string;
}) {
  const frame: CSSProperties = {
    position: "absolute",
    left: element.rect.x_mm * MM_TO_PX,
    top: element.rect.y_mm * MM_TO_PX,
    width: element.rect.w_mm * MM_TO_PX,
    height: element.rect.h_mm * MM_TO_PX,
    transform: element.rotation_deg ? `rotate(${element.rotation_deg}deg)` : undefined,
    zIndex: element.z + 1000,
    overflow: "hidden",
  };

  if (element.type === "text") {
    return (
      <div style={frame}>
        <div style={textStyle(element, resolveSample(element.content, fields))}>
          {resolveSample(element.content, fields)}
        </div>
      </div>
    );
  }

  if (element.type === "image") {
    return (
      <div style={frame}>
        <ImageView element={element} t={t} />
      </div>
    );
  }

  if (element.type === "shape") {
    if (element.shape === "line") {
      return (
        <div
          style={{
            ...frame,
            borderTop: `${Math.max(0.3, element.stroke?.width_mm ?? 0.4) * MM_TO_PX}px solid ${element.stroke?.colour ?? "var(--doc-ink-muted)"}`,
            height: 0,
          }}
        />
      );
    }
    return (
      <div
        style={{
          ...frame,
          background: element.fill,
          border: element.stroke?.width_mm
            ? `${element.stroke.width_mm * MM_TO_PX}px solid ${element.stroke.colour}`
            : undefined,
          borderRadius: element.shape === "ellipse" ? "50%" : `${element.radius_mm * MM_TO_PX}px`,
        }}
      />
    );
  }

  if (element.type === "table") {
    return (
      <div style={frame}>
        <TableView element={element} fields={fields} />
      </div>
    );
  }

  if (element.type === "qr") {
    return (
      <div style={frame} className="doc-qr" aria-label={t("documents.editor.add_qr")}>
        <span>{t("documents.editor.add_qr")}</span>
        <code>{element.data}</code>
      </div>
    );
  }

  return (
    <div style={frame} className="doc-barcode" aria-label={t("documents.editor.add_barcode")}>
      <div
        className="doc-barcode__bars"
        style={{ background: `repeating-linear-gradient(90deg, ${element.foreground} 0 2px, ${element.background} 2px 4px, ${element.foreground} 4px 5px, ${element.background} 5px 8px)` }}
      />
      {element.show_text ? <code>{element.data}</code> : null}
    </div>
  );
}

export function elementDescription(
  element: LayoutElement,
  fields: Map<string, FieldDefinition>,
): string {
  if (element.type === "text") return resolveSample(element.content, fields);
  if (element.type === "image") return element.source.value;
  if (element.type === "table") return element.table.source;
  if (element.type === "qr" || element.type === "barcode") return element.data;
  return element.shape;
}

export function sampleForId(fields: Map<string, FieldDefinition>, key: string): string {
  return sampleFor(fields.get(key));
}
