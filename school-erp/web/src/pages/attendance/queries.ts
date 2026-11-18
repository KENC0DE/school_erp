import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type {
  SessionDetail,
  SessionFilters,
  SessionList,
} from "./types";

export const ATTENDANCE = "/api/v1/attendance";

export function withQuery(
  path: string,
  params: Record<string, string | number | undefined>,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export function filterParams(filters: SessionFilters): Record<string, string> {
  return {
    year_id: filters.year_id,
    section_id: filters.section_id,
    from_date: filters.date,
    to_date: filters.date,
    status: filters.status,
  };
}

export function useSessions(filters: SessionFilters) {
  return useQuery({
    queryKey: ["attendance", "sessions", filters],
    queryFn: () => api.get<SessionList>(withQuery(ATTENDANCE, filterParams(filters))),
    enabled: Boolean(filters.year_id),
    retry: false,
  });
}

export function useSessionDetail(sessionId: string | null) {
  return useQuery({
    queryKey: ["attendance", "session", sessionId],
    queryFn: () => api.get<SessionDetail>(`${ATTENDANCE}/${sessionId}`),
    enabled: Boolean(sessionId),
    retry: false,
  });
}
