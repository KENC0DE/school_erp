import type { Layout, LayoutElement } from "@erp/documents";
import { useCallback, useMemo, useRef, useState } from "react";

const LIMIT = 60;

interface HistoryState {
  past: Layout[];
  present: Layout;
  future: Layout[];
}

export interface LayoutHistory {
  layout: Layout;
  dirty: boolean;
  canUndo: boolean;
  canRedo: boolean;
  /** Commit a change as one undoable step. */
  commit: (next: Layout | ((current: Layout) => Layout)) => void;
  /** Snapshot the current layout once, then apply live changes during a drag. */
  beginGesture: () => void;
  updateLive: (next: Layout | ((current: Layout) => Layout)) => void;
  undo: () => void;
  redo: () => void;
  reset: (layout: Layout) => void;
  markSaved: (layout: Layout) => void;
}

function same(a: Layout, b: Layout): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function useLayoutHistory(initial: Layout): LayoutHistory {
  const [state, setState] = useState<HistoryState>({
    past: [],
    present: initial,
    future: [],
  });
  const [saved, setSaved] = useState<string>(JSON.stringify(initial));
  const gestureOpen = useRef(false);

  const commit = useCallback((next: Layout | ((current: Layout) => Layout)) => {
    setState((current) => {
      const value = typeof next === "function" ? next(current.present) : next;
      if (same(value, current.present)) return current;
      return {
        past: [...current.past, current.present].slice(-LIMIT),
        present: value,
        future: [],
      };
    });
    gestureOpen.current = false;
  }, []);

  const beginGesture = useCallback(() => {
    if (gestureOpen.current) return;
    gestureOpen.current = true;
    setState((current) => ({
      past: [...current.past, current.present].slice(-LIMIT),
      present: current.present,
      future: [],
    }));
  }, []);

  const updateLive = useCallback((next: Layout | ((current: Layout) => Layout)) => {
    setState((current) => ({
      ...current,
      present: typeof next === "function" ? next(current.present) : next,
    }));
  }, []);

  const undo = useCallback(() => {
    gestureOpen.current = false;
    setState((current) => {
      const previous = current.past.at(-1);
      if (!previous) return current;
      return {
        past: current.past.slice(0, -1),
        present: previous,
        future: [current.present, ...current.future].slice(0, LIMIT),
      };
    });
  }, []);

  const redo = useCallback(() => {
    gestureOpen.current = false;
    setState((current) => {
      const next = current.future[0];
      if (!next) return current;
      return {
        past: [...current.past, current.present].slice(-LIMIT),
        present: next,
        future: current.future.slice(1),
      };
    });
  }, []);

  const reset = useCallback((layout: Layout) => {
    setSaved(JSON.stringify(layout));
    gestureOpen.current = false;
    setState({ past: [], present: layout, future: [] });
  }, []);

  const markSaved = useCallback((layout: Layout) => {
    setSaved(JSON.stringify(layout));
  }, []);

  return useMemo(
    () => ({
      layout: state.present,
      dirty: JSON.stringify(state.present) !== saved,
      canUndo: state.past.length > 0,
      canRedo: state.future.length > 0,
      commit,
      beginGesture,
      updateLive,
      undo,
      redo,
      reset,
      markSaved,
    }),
    [state, saved, commit, beginGesture, updateLive, undo, redo, reset, markSaved],
  );
}

/** Replace one element, leaving the rest of the layout untouched. */
export function patchElement(
  layout: Layout,
  id: string,
  patch: Partial<LayoutElement>,
): Layout {
  return {
    ...layout,
    elements: layout.elements.map((element) =>
      element.id === id ? ({ ...element, ...patch } as LayoutElement) : element,
    ),
  };
}

export function patchElementRect(
  layout: Layout,
  id: string,
  rect: Partial<LayoutElement["rect"]>,
): Layout {
  return {
    ...layout,
    elements: layout.elements.map((element) =>
      element.id === id ? { ...element, rect: { ...element.rect, ...rect } } : element,
    ),
  };
}

export function nextElementName(layout: Layout, type: string): string {
  const count = layout.elements.filter((element) => element.type === type).length + 1;
  return `${type} ${count}`;
}
