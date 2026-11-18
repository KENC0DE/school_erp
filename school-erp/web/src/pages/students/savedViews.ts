import type { SavedView, StudentFilters } from "./types";

const STORAGE_KEY = "erp.students.saved_views";

export const EMPTY_FILTERS: StudentFilters = {
  q: "",
  status: "",
  year_id: "",
  level_id: "",
  section_id: "",
};

export function loadSavedViews(): SavedView[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is SavedView =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as SavedView).id === "string" &&
        typeof (item as SavedView).name === "string" &&
        typeof (item as SavedView).filters === "object",
    );
  } catch {
    return [];
  }
}

export function persistSavedViews(views: SavedView[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(views));
}

export function newViewId(): string {
  return `view-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
