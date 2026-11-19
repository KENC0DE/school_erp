import { SessionError } from "../session/session";
import { forSchool } from "../storage/schoolStorage";
import { saveRecords } from "./api";
import type { RecordInput, SessionDetail } from "./types";

const OUTBOX_CACHE = "attendance.outbox";

export interface PendingRecord extends RecordInput {
  session_id: string;
  queued_at: string;
}

export interface FlushResult {
  sent: number;
  pending: number;
}

export interface SaveResult {
  detail: SessionDetail | null;
  queued: number;
}

type Sender = (
  instanceId: string,
  sessionId: string,
  items: RecordInput[],
) => Promise<SessionDetail>;

function key(entry: PendingRecord): string {
  return `${entry.session_id}:${entry.student_id}`;
}

function isPending(value: unknown): value is PendingRecord {
  const entry = value as Partial<PendingRecord> | null;
  return Boolean(
    entry &&
      typeof entry.session_id === "string" &&
      typeof entry.student_id === "string" &&
      typeof entry.status === "string" &&
      typeof entry.queued_at === "string",
  );
}

export async function loadOutbox(instanceId: string): Promise<PendingRecord[]> {
  const stored = await forSchool(instanceId).getCache<unknown>(OUTBOX_CACHE);
  if (!Array.isArray(stored)) return [];
  return stored.filter(isPending);
}

async function writeOutbox(instanceId: string, entries: PendingRecord[]): Promise<void> {
  await forSchool(instanceId).setCache(OUTBOX_CACHE, entries);
}

/**
 * Queues entries by the natural key `(session, student)`. Repeating an entry
 * offline replaces the earlier one, so a long offline session still replays one
 * row per student and the server upsert stays idempotent.
 */
export async function queueRecords(
  instanceId: string,
  sessionId: string,
  items: RecordInput[],
): Promise<PendingRecord[]> {
  const current = await loadOutbox(instanceId);
  const merged = new Map(current.map((entry) => [key(entry), entry]));
  const queuedAt = new Date().toISOString();
  for (const item of items) {
    const entry: PendingRecord = { ...item, session_id: sessionId, queued_at: queuedAt };
    merged.set(key(entry), entry);
  }
  const next = Array.from(merged.values());
  await writeOutbox(instanceId, next);
  return next;
}

/** Saves directly, or queues the entries when the device is offline. */
export async function saveOrQueue(
  instanceId: string,
  sessionId: string,
  items: RecordInput[],
  send: Sender = saveRecords,
): Promise<SaveResult> {
  try {
    return { detail: await send(instanceId, sessionId, items), queued: 0 };
  } catch (caught) {
    if (caught instanceof SessionError && caught.code === "NETWORK_ERROR") {
      const pending = await queueRecords(instanceId, sessionId, items);
      return { detail: null, queued: pending.length };
    }
    throw caught;
  }
}

/**
 * Replays every pending entry once, grouped by session. A failed group stays in
 * the outbox so the next reconnect retries it; a group that succeeds is removed.
 * The replay is safe to repeat because the API upserts on `(session, student)`.
 */
export async function flushOutbox(
  instanceId: string,
  send: Sender = saveRecords,
): Promise<FlushResult> {
  const pending = await loadOutbox(instanceId);
  if (pending.length === 0) return { sent: 0, pending: 0 };

  const groups = new Map<string, PendingRecord[]>();
  for (const entry of pending) {
    const group = groups.get(entry.session_id) ?? [];
    group.push(entry);
    groups.set(entry.session_id, group);
  }

  let sent = 0;
  const remaining: PendingRecord[] = [];
  for (const [sessionId, entries] of groups) {
    const items: RecordInput[] = entries.map((entry) => ({
      student_id: entry.student_id,
      status: entry.status,
      reason: entry.reason,
      late_minutes: entry.late_minutes,
      note: entry.note,
      row_version: entry.row_version,
    }));
    try {
      await send(instanceId, sessionId, items);
      sent += entries.length;
    } catch {
      remaining.push(...entries);
    }
  }
  await writeOutbox(instanceId, remaining);
  return { sent, pending: remaining.length };
}
