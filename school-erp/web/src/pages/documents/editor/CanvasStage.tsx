import type { Layout, LayoutElement } from "@erp/documents";
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { FieldDefinition } from "../types";
import { pageSizeMm } from "../types";
import { ElementView, MM_TO_PX } from "./ElementView";
import { clampToPage } from "./elements";
import { patchElementRect } from "./history";
import {
  resizeRect,
  snapMove,
  snapResize,
  type ResizeHandle,
} from "./snapping";

const HANDLES: ResizeHandle[] = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];

interface DragState {
  id: string;
  mode: "move" | "resize";
  handle?: ResizeHandle;
  startX: number;
  startY: number;
  origin: LayoutElement["rect"];
}

export interface CanvasStageProps {
  layout: Layout;
  selectedId: string | null;
  fields: Map<string, FieldDefinition>;
  t: (key: string) => string;
  zoom: number;
  snap: boolean;
  readOnly?: boolean;
  onSelect: (id: string | null) => void;
  onBeginGesture: () => void;
  onChange: (layout: Layout) => void;
}

export function CanvasStage({
  layout,
  selectedId,
  fields,
  t,
  zoom,
  snap,
  readOnly = false,
  onSelect,
  onBeginGesture,
  onChange,
}: CanvasStageProps) {
  const [drag, setDrag] = useState<DragState | null>(null);
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  const page = pageSizeMm(layout.page);
  const pageWidth = page.width * MM_TO_PX;
  const pageHeight = page.height * MM_TO_PX;
  const selected = layout.elements.find((element) => element.id === selectedId) ?? null;

  useEffect(() => {
    if (!drag) return;
    const onMove = (event: PointerEvent) => {
      const deltaMm = {
        x: (event.clientX - drag.startX) / (zoom * MM_TO_PX),
        y: (event.clientY - drag.startY) / (zoom * MM_TO_PX),
      };
      const element = layoutRef.current.elements.find((item) => item.id === drag.id);
      if (!element) return;
      const rect =
        drag.mode === "move"
          ? snapMove(
              layoutRef.current,
              element,
              {
                ...drag.origin,
                x_mm: drag.origin.x_mm + deltaMm.x,
                y_mm: drag.origin.y_mm + deltaMm.y,
              },
              snap,
            )
          : snapResize(resizeRect(drag.handle ?? "se", drag.origin, deltaMm.x, deltaMm.y));
      onChange(patchElementRect(layoutRef.current, drag.id, rect));
    };
    const onUp = () => setDrag(null);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [drag, zoom, snap, onChange]);

  const start = (event: ReactPointerEvent, element: LayoutElement) => {
    if (readOnly || element.locked) return;
    event.stopPropagation();
    onSelect(element.id);
    onBeginGesture();
    setDrag({
      id: element.id,
      mode: "move",
      startX: event.clientX,
      startY: event.clientY,
      origin: { ...element.rect },
    });
  };

  const startResize = (event: ReactPointerEvent, element: LayoutElement, handle: ResizeHandle) => {
    if (readOnly || element.locked) return;
    event.stopPropagation();
    onSelect(element.id);
    onBeginGesture();
    setDrag({
      id: element.id,
      mode: "resize",
      handle,
      startX: event.clientX,
      startY: event.clientY,
      origin: { ...element.rect },
    });
  };

  return (
    <div className="doc-canvas-scroll" data-testid="doc-canvas">
      <div
        className="doc-canvas-scale"
        style={{ width: pageWidth * zoom, height: pageHeight * zoom }}
      >
        <div
          className="doc-page"
          data-testid="doc-page"
          style={{
            width: pageWidth,
            height: pageHeight,
            transform: `scale(${zoom})`,
            background: layout.page.background_colour ?? "var(--doc-paper)",
          }}
          onPointerDown={() => onSelect(null)}
        >
          <div
            className="doc-margin-guide"
            aria-hidden="true"
            style={{
              left: layout.page.margins_mm.left * MM_TO_PX,
              top: layout.page.margins_mm.top * MM_TO_PX,
              right: layout.page.margins_mm.right * MM_TO_PX,
              bottom: layout.page.margins_mm.bottom * MM_TO_PX,
            }}
          />
          {[...layout.elements]
            .sort((a, b) => a.z - b.z)
            .map((element) => (
              <div
                key={element.id}
                className={`doc-element${selectedId === element.id ? " doc-element--selected" : ""}${element.locked ? " doc-element--locked" : ""}`}
                data-testid={`doc-element-${element.id}`}
                onPointerDown={(event) => start(event, element)}
              >
                <ElementView element={element} fields={fields} t={t} />
              </div>
            ))}
          {selected ? (
            <div
              className="doc-selection"
              data-testid="doc-selection"
              style={{
                left: selected.rect.x_mm * MM_TO_PX,
                top: selected.rect.y_mm * MM_TO_PX,
                width: selected.rect.w_mm * MM_TO_PX,
                height: selected.rect.h_mm * MM_TO_PX,
                transform: selected.rotation_deg
                  ? `rotate(${selected.rotation_deg}deg)`
                  : undefined,
              }}
            >
              {HANDLES.map((handle) => (
                <button
                  key={handle}
                  type="button"
                  className={`doc-handle doc-handle--${handle}`}
                  aria-label={handle}
                  data-testid={`doc-handle-${handle}`}
                  disabled={readOnly || selected.locked}
                  onPointerDown={(event) => startResize(event, selected, handle)}
                />
              ))}
              {selected.locked ? (
                <span className="doc-selection__lock" aria-label={t("documents.editor.locked")}>
                  🔒
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** Keep an element on the page after a numeric inspector edit. */
export function normaliseRect(layout: Layout, element: LayoutElement): LayoutElement {
  return { ...element, rect: clampToPage(layout, element.rect) };
}
