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


export type ScaleType = "numeric_bands" | "descriptive";
export type ScaleContext = "assessment" | "subject" | "level" | "stage" | "default";

export interface BandOut {
  id: string;
  min_value: string;
  max_value: string;
  label: string;
  remark: string | null;
  gpa_points: string | null;
  is_pass: boolean;
  color: string | null;
  sort_order: number;
  row_version: number;
}

export interface GradeScale {
  id: string;
  name: string;
  name_am: string | null;
  type: ScaleType;
  description: string | null;
  is_default: boolean;
  lower_bound: string;
  upper_bound: string;
  precision: number;
  rounding: Rounding;
  version: number;
  effective_from: string | null;
  effective_to: string | null;
  is_active: boolean;
  notes: string | null;
  row_version: number;
  bands: BandOut[];
  assignment_count: number;
}

export interface GradeScaleList {
  items: GradeScale[];
  total: number;
}

export interface BandDraft {
  id: string | null;
  min_value: string;
  label: string;
  remark: string;
  gpa_points: string;
  is_pass: boolean;
  color: string;
}

export interface ScaleDraft {
  id: string | null;
  row_version: number | null;
  name: string;
  name_am: string;
  type: ScaleType;
  description: string;
  is_default: boolean;
  lower_bound: string;
  upper_bound: string;
  precision: string;
  rounding: Rounding;
  effective_from: string;
  effective_to: string;
  is_active: boolean;
  bands: BandDraft[];
}

export interface ScaleTestResult {
  value: string;
  label: string;
  remark: string | null;
  gpa_points: string | null;
  is_pass: boolean;
  color: string | null;
  band_min: string;
  band_max: string;
  scale_name: string;
  scale_version: number;
}

export interface ScaleAssignment {
  id: string;
  scale_id: string;
  scale_name: string;
  context: ScaleContext;
  scope_key: string;
  assessment_id: string | null;
  assessment_title: string | null;
  subject_id: string | null;
  subject_name: string | null;
  level_id: string | null;
  level_name: string | null;
  stage_id: string | null;
  stage_name: string | null;
  notes: string | null;
  row_version: number;
}

export interface ScaleAssignmentList {
  items: ScaleAssignment[];
  total: number;
}

export interface AssessmentSummary {
  id: string;
  title: string;
  year_id: string;
  term_name: string;
  section_code: string;
  subject_name: string;
  component_name: string;
}

export interface AssessmentSummaryList {
  items: AssessmentSummary[];
  next_cursor: string | null;
  total: number | null;
}

export const SCALE_TYPES: ScaleType[] = ["numeric_bands", "descriptive"];
export const SCALE_CONTEXTS: ScaleContext[] = [
  "default",
  "stage",
  "level",
  "subject",
  "assessment",
];

export function emptyBand(): BandDraft {
  return {
    id: null,
    min_value: "",
    label: "",
    remark: "",
    gpa_points: "",
    is_pass: true,
    color: "",
  };
}

export function emptyScaleDraft(): ScaleDraft {
  return {
    id: null,
    row_version: null,
    name: "",
    name_am: "",
    type: "numeric_bands",
    description: "",
    is_default: false,
    lower_bound: "0",
    upper_bound: "100",
    precision: "2",
    rounding: "half_up",
    effective_from: "",
    effective_to: "",
    is_active: true,
    bands: [{ ...emptyBand(), min_value: "0" }],
  };
}

export function scaleDraftFrom(scale: GradeScale): ScaleDraft {
  const ordered = [...scale.bands].sort(
    (left, right) => left.sort_order - right.sort_order || left.min_value.localeCompare(right.min_value),
  );
  return {
    id: scale.id,
    row_version: scale.row_version,
    name: scale.name,
    name_am: scale.name_am ?? "",
    type: scale.type,
    description: scale.description ?? "",
    is_default: scale.is_default,
    lower_bound: scale.lower_bound,
    upper_bound: scale.upper_bound,
    precision: String(scale.precision),
    rounding: scale.rounding,
    effective_from: scale.effective_from ?? "",
    effective_to: scale.effective_to ?? "",
    is_active: scale.is_active,
    bands: ordered.map((band) => ({
      id: band.id,
      min_value: band.min_value,
      label: band.label,
      remark: band.remark ?? "",
      gpa_points: band.gpa_points ?? "",
      is_pass: band.is_pass,
      color: band.color ?? "",
    })),
  };
}

/** The upper edge of band ``index``: the next band's start, or the scale's top. */
export function bandTo(draft: ScaleDraft, index: number): string {
  return index < draft.bands.length - 1 ? draft.bands[index + 1].min_value : draft.upper_bound;
}

/** A scale's bands must start at its lower bound, keep rising and stop below the top. */
export function scaleBandsValid(draft: ScaleDraft): boolean {
  if (draft.bands.length === 0) return false;
  const lower = toMicro(draft.lower_bound);
  const upper = toMicro(draft.upper_bound);
  if (lower === null || upper === null || lower >= upper) return false;
  let previous: bigint | null = null;
  for (const [index, band] of draft.bands.entries()) {
    if (!band.label.trim()) return false;
    if (band.gpa_points.trim() && toMicro(band.gpa_points) === null) return false;
    const min = toMicro(band.min_value);
    if (min === null) return false;
    if (index === 0 && min !== lower) return false;
    if (previous !== null && min <= previous) return false;
    previous = min;
  }
  return previous !== null && previous < upper;
}

/** Split the widest band so a new boundary becomes editable; null when impossible. */
export function splitBand(draft: ScaleDraft): BandDraft[] | null {
  let choice = -1;
  let width = 0n;
  for (const [index, band] of draft.bands.entries()) {
    const min = toMicro(band.min_value);
    const max = toMicro(bandTo(draft, index));
    if (min === null || max === null) continue;
    const span = max - min;
    if (span > width) {
      width = span;
      choice = index;
    }
  }
  if (choice < 0 || width <= 1n) return null;
  const min = toMicro(draft.bands[choice].min_value);
  if (min === null) return null;
  const middle = fromMicro(min + width / 2n);
  const next = [...draft.bands];
  next.splice(choice + 1, 0, {
    ...emptyBand(),
    min_value: middle,
    is_pass: draft.bands[choice].is_pass,
  });
  return next;
}

export function assignmentTargetName(assignment: ScaleAssignment): string | null {
  if (assignment.context === "assessment") return assignment.assessment_title;
  if (assignment.context === "subject") return assignment.subject_name;
  if (assignment.context === "level") return assignment.level_name;
  if (assignment.context === "stage") return assignment.stage_name;
  return null;
}

export type ScoreStatus = "present" | "absent" | "excused" | "exempt" | "not_taken";

export const SCORE_STATUSES: ScoreStatus[] = [
  "present",
  "absent",
  "excused",
  "exempt",
  "not_taken",
];

export interface ScoreOut {
  score_id: string | null;
  student_id: string;
  student_number: string;
  student_name: string;
  student_name_am: string | null;
  roll_number: string | null;
  enrolled: boolean;
  raw_score: string | null;
  out_of: string;
  status: ScoreStatus;
  converted: string | null;
  note: string | null;
  row_version: number | null;
  entered_at: string | null;
}

export interface ScoreStats {
  total: number;
  entered: number;
  missing: number;
  present: number;
  absent: number;
  excused: number;
  exempt: number;
  not_taken: number;
  out_of: string;
  component_max_points: string;
  average_converted: string | null;
  average_percent: string | null;
  highest_converted: string | null;
  lowest_converted: string | null;
}

export interface ScoreSheet {
  assessment_id: string;
  title: string;
  component_key: string;
  component_max_points: string;
  out_of: string;
  allow_bonus: boolean;
  editable: boolean;
  items: ScoreOut[];
  stats: ScoreStats;
}

export interface ScoreBulkResult {
  sheet: ScoreSheet;
  created: number;
  updated: number;
  unchanged: number;
}

export interface MarkingWindow {
  id: string;
  year_id: string;
  term_id: string;
  level_id: string | null;
  section_id: string | null;
  scope_key: string;
  opens_at: string;
  closes_at: string;
  is_active: boolean;
  state: "open" | "scheduled" | "closed";
  note: string | null;
  row_version: number;
}

export interface MarkingWindowList {
  items: MarkingWindow[];
  next_cursor: string | null;
  total: number | null;
}

export interface Submission {
  id: string;
  year_id: string;
  year_code: string;
  term_id: string;
  section_id: string;
  section_code: string;
  subject_id: string;
  subject_name: string;
  status: "draft" | "submitted" | "approved" | "published" | "locked";
  submitted_at: string | null;
  approved_at: string | null;
  published_at: string | null;
  locked_at: string | null;
  note: string | null;
  assessments: number;
  scores: number;
  entered: number;
  row_version: number;
}

export interface SubmissionList {
  items: Submission[];
  next_cursor: string | null;
  total: number | null;
}

export interface AssessmentListItem extends AssessmentSummary {
  year_code: string;
  term_id: string;
  section_id: string;
  level_id: string;
  level_name: string;
  subject_id: string;
  component_id: string;
  component_max_points: string;
  assessment_date: string;
  out_of: string;
  component_key: string;
  allow_bonus: boolean;
  status: string;
  scores: number;
  entered: number;
  row_version: number;
}

export interface AssessmentList {
  items: AssessmentListItem[];
  next_cursor: string | null;
  total: number | null;
}
