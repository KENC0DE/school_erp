import type { Layout, LayoutElement } from "@erp/documents";

import { pageSizeMm } from "../types";
import { clampToPage } from "./elements";

const THRESHOLD_MM = 1.6;

function candidates(layout: Layout, ignore: string): number[] {
  const page = pageSizeMm(layout.page);
  const margin = layout.page.margins_mm;
  const values = [
    0,
    margin.left,
    page.width / 2,
    page.width - margin.right,
    page.width,
  ];
  for (const element of layout.elements) {
    if (element.id === ignore) continue;
    values.push(
      element.rect.x_mm,
      element.rect.x_mm + element.rect.w_mm / 2,
      element.rect.x_mm + element.rect.w_mm,
    );
  }
  return values;
}

function verticalCandidates(layout: Layout, ignore: string): number[] {
  const page = pageSizeMm(layout.page);
  const margin = layout.page.margins_mm;
  const values = [
    0,
    margin.top,
    page.height / 2,
    page.height - margin.bottom,
    page.height,
  ];
  for (const element of layout.elements) {
    if (element.id === ignore) continue;
    values.push(
      element.rect.y_mm,
      element.rect.y_mm + element.rect.h_mm / 2,
      element.rect.y_mm + element.rect.h_mm,
    );
  }
  return values;
}

function nearest(value: number, targets: number[]): number | null {
  let best: number | null = null;
  let bestDistance = THRESHOLD_MM;
  for (const target of targets) {
    const distance = Math.abs(target - value);
    if (distance <= bestDistance) {
      best = target;
      bestDistance = distance;
    }
  }
  return best;
}

/**
 * Snap a moved rectangle to the page margins, centre line and other elements.
 * The element edge nearest a guide wins; when nothing is near, the 1 mm grid
 * keeps positions tidy.
 */
export function snapMove(
  layout: Layout,
  element: LayoutElement,
  rect: LayoutElement["rect"],
  enabled: boolean,
): LayoutElement["rect"] {
  let next = { ...rect };
  if (enabled) {
    const xTargets = candidates(layout, element.id);
    const yTargets = verticalCandidates(layout, element.id);
    const left = nearest(next.x_mm, xTargets);
    const right = nearest(next.x_mm + next.w_mm, xTargets);
    const centre = nearest(next.x_mm + next.w_mm / 2, xTargets);
    if (left !== null) next.x_mm = left;
    else if (right !== null) next.x_mm = right - next.w_mm;
    else if (centre !== null) next.x_mm = centre - next.w_mm / 2;

    const top = nearest(next.y_mm, yTargets);
    const bottom = nearest(next.y_mm + next.h_mm, yTargets);
    const middle = nearest(next.y_mm + next.h_mm / 2, yTargets);
    if (top !== null) next.y_mm = top;
    else if (bottom !== null) next.y_mm = bottom - next.h_mm;
    else if (middle !== null) next.y_mm = middle - next.h_mm / 2;
  }
  next = {
    ...next,
    x_mm: Math.round(next.x_mm * 10) / 10,
    y_mm: Math.round(next.y_mm * 10) / 10,
  };
  return clampToPage(layout, next);
}

export function snapResize(rect: LayoutElement["rect"]): LayoutElement["rect"] {
  return {
    x_mm: Math.round(rect.x_mm * 10) / 10,
    y_mm: Math.round(rect.y_mm * 10) / 10,
    w_mm: Math.max(2, Math.round(rect.w_mm * 10) / 10),
    h_mm: Math.max(0.5, Math.round(rect.h_mm * 10) / 10),
  };
}

export type ResizeHandle = "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";

export function resizeRect(
  handle: ResizeHandle,
  origin: LayoutElement["rect"],
  deltaX: number,
  deltaY: number,
): LayoutElement["rect"] {
  let { x_mm, y_mm, w_mm, h_mm } = origin;
  if (handle.includes("e")) w_mm = origin.w_mm + deltaX;
  if (handle.includes("s")) h_mm = origin.h_mm + deltaY;
  if (handle.includes("w")) {
    x_mm = origin.x_mm + deltaX;
    w_mm = origin.w_mm - deltaX;
  }
  if (handle.includes("n")) {
    y_mm = origin.y_mm + deltaY;
    h_mm = origin.h_mm - deltaY;
  }
  return {
    x_mm: w_mm < 2 ? origin.x_mm : x_mm,
    y_mm: h_mm < 1 ? origin.y_mm : y_mm,
    w_mm: Math.max(2, w_mm),
    h_mm: Math.max(1, h_mm),
  };
}
