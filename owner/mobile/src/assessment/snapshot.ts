import { forSchool } from "../storage/schoolStorage";
import type {
  AssessmentSummary,
  MarkingWindow,
  ScoreSheet,
  Submission,
} from "./types";

/** The last good read of one assessment, kept so marks can be entered offline. */
export interface SheetSnapshot {
  assessment: AssessmentSummary;
  sheet: ScoreSheet;
  windows: MarkingWindow[];
  submissions: Submission[];
}

function cacheName(assessmentId: string): string {
  return `assessment.sheet.${assessmentId}`;
}

function isSnapshot(value: unknown): value is SheetSnapshot {
  const snapshot = value as Partial<SheetSnapshot> | null;
  return Boolean(
    snapshot &&
      typeof snapshot.assessment === "object" &&
      snapshot.assessment !== null &&
      typeof snapshot.sheet === "object" &&
      snapshot.sheet !== null &&
      Array.isArray(snapshot.windows) &&
      Array.isArray(snapshot.submissions),
  );
}

export async function saveSnapshot(
  instanceId: string,
  snapshot: SheetSnapshot,
): Promise<void> {
  await forSchool(instanceId).setCache(
    cacheName(snapshot.assessment.id),
    snapshot,
  );
}

export async function loadSnapshot(
  instanceId: string,
  assessmentId: string,
): Promise<SheetSnapshot | null> {
  const stored = await forSchool(instanceId).getCache<unknown>(
    cacheName(assessmentId),
  );
  return isSnapshot(stored) ? stored : null;
}
