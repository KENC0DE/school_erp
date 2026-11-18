import { authorizedJson } from "../session/session";
import type { StaffDetail, StaffFilters, StaffList } from "./types";

const STAFF = "/api/v1/staff";

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const suffix = search.toString();
  return suffix ? `?${suffix}` : "";
}

export function listStaff(
  instanceId: string,
  filters: StaffFilters,
  cursor?: string | null,
): Promise<StaffList> {
  return authorizedJson<StaffList>(
    instanceId,
    `${STAFF}${query({
      q: filters.q?.trim(),
      status: filters.status,
      cursor: cursor ?? undefined,
      limit: 25,
    })}`,
  );
}

export function getStaff(instanceId: string, staffId: string): Promise<StaffDetail> {
  return authorizedJson<StaffDetail>(instanceId, `${STAFF}/${staffId}`);
}
