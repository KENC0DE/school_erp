import { SessionError } from "../session/session";
import { forSchool } from "../storage/schoolStorage";
import { saveScores } from "./api";
import { isConflict } from "./errors";
import type { ScoreInput, ScoreSheet, ScoreStatus } from "./types";

const OUTBOX_CACHE = "assessment.outbox";

/** One queued mark, keyed by `(assessment, student)` so replays never duplicate. */
export interface PendingMark {
  assessment_id: string;
  student_id: string;
  raw_score: string | null;
  status: ScoreStatus;
  row_version: number | null;
  queued_at: string;
}

export interface QueueItem {
  student_id: string;
  raw_score: string | null;
  status: ScoreStatus;
  row_version: number | null;
}

export interface FlushResult {
  sent: number;
  pending: number;
  conflicts: PendingMark[];
  failed: PendingMark[];
}

export interface SaveMarkResult {
  sheet: ScoreSheet | null;
  queued: number;
  conflict: boolean;
}

type Sender = (
  instanceId: string,
  assessmentId: string,
  item: ScoreInput,
) => Promise<ScoreSheet>;

async function sendOne(
  instanceId: string,
  assessmentId: string,
  item: ScoreInput,
): Promise<ScoreSheet> {
  const result = await saveScores(instanceId, assessmentId, [item]);
  return result.sheet;
}

function key(entry: { assessment_id: string; student_id: string }): string {
  return `${entry.assessment_id}:${entry.student_id}`;
}

function isPending(value: unknown): value is PendingMark {
  const entry = value as Partial<PendingMark> | null;
  return Boolean(
    entry &&
      typeof entry.assessment_id === "string" &&
      typeof entry.student_id === "string" &&
      typeof entry.status === "string" &&
      typeof entry.queued_at === "string",
  );
}

function toInput(entry: PendingMark): ScoreInput {
  return {
    student_id: entry.student_id,
    raw_score: entry.raw_score,
    status: entry.status,
    row_version: entry.row_version,
  };
}

export async function loadOutbox(instanceId: string): Promise<PendingMark[]> {
  const stored = await forSchool(instanceId).getCache<unknown>(OUTBOX_CACHE);
  if (!Array.isArray(stored)) return [];
  return stored.filter(isPending);
}

async function writeOutbox(
  instanceId: string,
  entries: PendingMark[],
): Promise<void> {
  await forSchool(instanceId).setCache(OUTBOX_CACHE, entries);
}

/** Merges entries into the outbox, replacing an older edit of the same mark. */
export async function queueMarks(
  instanceId: string,
  assessmentId: string,
  items: QueueItem[],
): Promise<PendingMark[]> {
  const current = await loadOutbox(instanceId);
  const merged = new Map(current.map((entry) => [key(entry), entry]));
  const queuedAt = new Date().toISOString();
  for (const item of items) {
    const entry: PendingMark = {
      ...item,
      assessment_id: assessmentId,
      queued_at: queuedAt,
    };
    merged.set(key(entry), entry);
  }
  const next = Array.from(merged.values());
  await writeOutbox(instanceId, next);
  return next;
}

/** Removes queued marks, used when the teacher accepts the server value. */
export async function discardMarks(
  instanceId: string,
  entries: Array<{ assessment_id: string; student_id: string }>,
): Promise<PendingMark[]> {
  const dropped = new Set(entries.map(key));
  const remaining = (await loadOutbox(instanceId)).filter(
    (entry) => !dropped.has(key(entry)),
  );
  await writeOutbox(instanceId, remaining);
  return remaining;
}

/** Saves one mark directly, or queues it when offline or when the row is stale. */
export async function saveOrQueue(
  instanceId: string,
  assessmentId: string,
  item: QueueItem,
  send: Sender = sendOne,
): Promise<SaveMarkResult> {
  try {
    const sheet = await send(instanceId, assessmentId, {
      student_id: item.student_id,
      raw_score: item.raw_score,
      status: item.status,
      row_version: item.row_version,
    });
    return { sheet, queued: 0, conflict: false };
  } catch (caught) {
    if (caught instanceof SessionError && caught.code === "NETWORK_ERROR") {
      const pending = await queueMarks(instanceId, assessmentId, [item]);
      return { sheet: null, queued: pending.length, conflict: false };
    }
    if (isConflict(caught)) {
      const pending = await queueMarks(instanceId, assessmentId, [item]);
      return { sheet: null, queued: pending.length, conflict: true };
    }
    throw caught;
  }
}

/**
 * Replays queued marks one row at a time. A row is removed only after the server
 * accepted it; offline rows and conflicts stay so the teacher can resolve them.
 * Entries are keyed by `(assessment, student)`, so repeating a flush cannot
 * create a second score for the same student.
 */
export async function flushOutbox(
  instanceId: string,
  send: Sender = sendOne,
): Promise<FlushResult> {
  const pending = await loadOutbox(instanceId);
  if (pending.length === 0)
    return { sent: 0, pending: 0, conflicts: [], failed: [] };

  let sent = 0;
  let offline = false;
  const remaining: PendingMark[] = [];
  const conflicts: PendingMark[] = [];
  const failed: PendingMark[] = [];

  for (const entry of pending) {
    if (offline) {
      remaining.push(entry);
      continue;
    }
    try {
      await send(instanceId, entry.assessment_id, toInput(entry));
      sent += 1;
    } catch (caught) {
      remaining.push(entry);
      if (isConflict(caught)) {
        conflicts.push(entry);
      } else {
        if (caught instanceof SessionError && caught.code === "NETWORK_ERROR")
          offline = true;
        failed.push(entry);
      }
    }
  }

  await writeOutbox(instanceId, remaining);
  return { sent, pending: remaining.length, conflicts, failed };
}
