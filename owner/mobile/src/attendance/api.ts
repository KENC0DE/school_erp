import { authorizedJson } from "../session/session";
import type {
  CreateSessionInput,
  RecordInput,
  SessionDetail,
  SessionFilters,
  SessionList,
} from "./types";

const ATTENDANCE = "/api/v1/attendance";

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const suffix = search.toString();
  return suffix ? `?${suffix}` : "";
}

export function listSessions(
  instanceId: string,
  filters: SessionFilters,
): Promise<SessionList> {
  return authorizedJson<SessionList>(
    instanceId,
    `${ATTENDANCE}${query({
      from_date: filters.date,
      to_date: filters.date,
      section_id: filters.section_id,
      limit: 50,
      order: "desc",
    })}`,
  );
}

export function getSession(instanceId: string, sessionId: string): Promise<SessionDetail> {
  return authorizedJson<SessionDetail>(instanceId, `${ATTENDANCE}/${sessionId}`);
}

export function createSession(
  instanceId: string,
  input: CreateSessionInput,
): Promise<SessionDetail> {
  return authorizedJson<SessionDetail>(instanceId, ATTENDANCE, {
    method: "POST",
    body: {
      ...input,
      period: input.period ?? undefined,
      notes: input.notes || null,
    },
  });
}

export function saveRecords(
  instanceId: string,
  sessionId: string,
  items: RecordInput[],
): Promise<SessionDetail> {
  return authorizedJson<SessionDetail>(instanceId, `${ATTENDANCE}/${sessionId}/records`, {
    method: "POST",
    body: { items },
  });
}

export function submitSession(instanceId: string, sessionId: string): Promise<SessionDetail> {
  return authorizedJson<SessionDetail>(instanceId, `${ATTENDANCE}/${sessionId}/submit`, {
    method: "POST",
  });
}
