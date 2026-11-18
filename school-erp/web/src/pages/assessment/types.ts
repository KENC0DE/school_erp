export type ScopeType = "school" | "stage" | "level" | "subject";
export type Aggregation = "average" | "weighted_average" | "best_n" | "sum_capped" | "latest";
export type YearMode = "average" | "sum" | "weighted_average";
export type Rounding = "half_up" | "half_even" | "half_down" | "up" | "down" | "ceiling" | "floor";

export interface ComponentOut {
  id: string;
  key: string;
  name: string;
  name_am: string | null;
  max_points: string;
  aggregation: Aggregation;
  absent_counts_as_zero: boolean;
  best_n: number | null;
  cap: string | null;
  sort_order: number;
  is_active: boolean;
  row_version: number;
}

export interface Structure {
  id: string;
  year_id: string;
  year_code: string;
  scope_type: ScopeType;
  scope_key: string;
  level_id: string | null;
  level_name: string | null;
  stage_id: string | null;
  stage_name: string | null;
  subject_id: string | null;
  subject_name: string | null;
  name: string;
  name_am: string | null;
  term_system: string;
  year_mode: YearMode;
  year_weights: string[] | null;
  precision: number;
  rounding: Rounding;
  intended_total: string | null;
  total: string;
  total_matches: boolean;
  descriptive_mode: boolean;
  version: number;
  is_active: boolean;
  row_version: number;
  components: ComponentOut[];
}

export interface StructureList {
  items: Structure[];
  next_cursor: string | null;
  total: number | null;
}

export interface ComponentDraft {
  id: string | null;
  key: string;
  name: string;
  name_am: string;
  max_points: string;
  aggregation: Aggregation;
  absent_zero: boolean;
  best_n: string;
  cap: string;
  is_active: boolean;
}

export interface StructureDraft {
  id: string | null;
  row_version: number | null;
  scope_type: ScopeType;
  level_id: string;
  stage_id: string;
  subject_id: string;
  name: string;
  name_am: string;
  year_mode: YearMode;
  year_weights: string[];
  precision: string;
  rounding: Rounding;
  intended_total: string;
  descriptive_mode: boolean;
  components: ComponentDraft[];
}

export interface Stage {
  id: string;
  code: string;
  name: string;
  name_am: string | null;
  sort_order: number;
  is_active: boolean;
  row_version: number;
}

export interface StageList {
  items: Stage[];
  total: number;
}

export const AGGREGATIONS: Aggregation[] = [
  "average",
  "weighted_average",
  "best_n",
  "sum_capped",
  "latest",
];

export const YEAR_MODES: YearMode[] = ["average", "sum", "weighted_average"];

export const ROUNDINGS: Rounding[] = [
  "half_up",
  "half_even",
  "half_down",
  "up",
  "down",
  "ceiling",
  "floor",
];

export const SCOPE_TYPES: ScopeType[] = ["school", "stage", "level", "subject"];

export function emptyComponent(index: number): ComponentDraft {
  return {
    id: null,
    key: `component_${index + 1}`,
    name: "",
    name_am: "",
    max_points: "",
    aggregation: "average",
    absent_zero: false,
    best_n: "",
    cap: "",
    is_active: true,
  };
}

export function emptyDraft(): StructureDraft {
  return {
    id: null,
    row_version: null,
    scope_type: "school",
    level_id: "",
    stage_id: "",
    subject_id: "",
    name: "",
    name_am: "",
    year_mode: "average",
    year_weights: [],
    precision: "2",
    rounding: "half_up",
    intended_total: "100",
    descriptive_mode: false,
    components: [emptyComponent(0)],
  };
}

export function draftFrom(structure: Structure): StructureDraft {
  return {
    id: structure.id,
    row_version: structure.row_version,
    scope_type: structure.scope_type,
    level_id: structure.level_id ?? "",
    stage_id: structure.stage_id ?? "",
    subject_id: structure.subject_id ?? "",
    name: structure.name,
    name_am: structure.name_am ?? "",
    year_mode: structure.year_mode,
    year_weights: structure.year_weights ?? [],
    precision: String(structure.precision),
    rounding: structure.rounding,
    intended_total: structure.intended_total ?? "",
    descriptive_mode: structure.descriptive_mode,
    components: structure.components.map((component) => ({
      id: component.id,
      key: component.key,
      name: component.name,
      name_am: component.name_am ?? "",
      max_points: component.max_points,
      aggregation: component.aggregation,
      absent_zero: component.absent_counts_as_zero,
      best_n: component.best_n === null ? "" : String(component.best_n),
      cap: component.cap ?? "",
      is_active: component.is_active,
    })),
  };
}

const MICRO = 1_000_000n;

/** Parse a decimal string into exact micro-units, or null when invalid. */
export function toMicro(value: string): bigint | null {
  const trimmed = value.trim();
  if (!/^\d+(\.\d{1,6})?$/.test(trimmed)) return null;
  const [whole, fraction = ""] = trimmed.split(".");
  return BigInt(whole) * MICRO + BigInt((fraction + "000000").slice(0, 6));
}

/** Render micro-units as the shortest exact decimal string. */
export function fromMicro(value: bigint): string {
  const whole = value / MICRO;
  const fraction = (value % MICRO).toString().padStart(6, "0").replace(/0+$/, "");
  return fraction ? `${whole}.${fraction}` : `${whole}`;
}

/** Sum component maxima exactly, without floating point. */
export function componentsTotal(components: ComponentDraft[]): bigint | null {
  let total = 0n;
  for (const component of components) {
    if (!component.max_points.trim()) continue;
    const value = toMicro(component.max_points);
    if (value === null) return null;
    total += value;
  }
  return total;
}

