import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type {
  ContractList,
  DepartmentList,
  DocumentList,
  LeaveBalanceList,
  LeaveCalendar,
  LeaveRequestList,
  LeaveTypeList,
  PositionList,
  QualificationList,
  StaffDetail,
  StaffFilters,
  StaffList,
  TeachingAssignmentList,
} from "./types";

export const STAFF = "/api/v1/staff";

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

function filterParams(
  filters: StaffFilters,
  cursor?: string | null,
): Record<string, string> {
  return {
    q: filters.q.trim(),
    status: filters.status,
    department_id: filters.department_id,
    position_id: filters.position_id,
    ...(cursor ? { cursor } : {}),
  };
}

export function useStaff(filters: StaffFilters, cursor: string | null) {
  return useQuery({
    queryKey: ["staff", "list", filters, cursor],
    queryFn: () => api.get<StaffList>(withQuery(STAFF, filterParams(filters, cursor))),
    retry: false,
  });
}

export function useStaffDetail(staffId: string | null) {
  return useQuery({
    queryKey: ["staff", "detail", staffId],
    queryFn: () => api.get<StaffDetail>(`${STAFF}/${staffId}`),
    enabled: Boolean(staffId),
    retry: false,
  });
}

export function useDepartments(includeInactive = false) {
  return useQuery({
    queryKey: ["staff", "departments", includeInactive],
    queryFn: () =>
      api.get<DepartmentList>(
        withQuery(`${STAFF}/departments`, {
          include_inactive: includeInactive ? "true" : undefined,
        }),
      ),
    retry: false,
  });
}

export function usePositions(departmentId = "", includeInactive = false) {
  return useQuery({
    queryKey: ["staff", "positions", departmentId, includeInactive],
    queryFn: () =>
      api.get<PositionList>(
        withQuery(`${STAFF}/positions`, {
          department_id: departmentId,
          include_inactive: includeInactive ? "true" : undefined,
        }),
      ),
    retry: false,
  });
}

export function useStaffContracts(staffId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["staff", "contracts", staffId],
    queryFn: () => api.get<ContractList>(`${STAFF}/${staffId}/contracts`),
    enabled: Boolean(staffId) && enabled,
    retry: false,
  });
}

export function useQualifications(staffId: string | null) {
  return useQuery({
    queryKey: ["staff", "qualifications", staffId],
    queryFn: () => api.get<QualificationList>(`${STAFF}/${staffId}/qualifications`),
    enabled: Boolean(staffId),
    retry: false,
  });
}

export function useTeachingAssignments(staffId: string | null) {
  return useQuery({
    queryKey: ["staff", "teaching", staffId],
    queryFn: () =>
      api.get<TeachingAssignmentList>(`${STAFF}/${staffId}/teaching-assignments`),
    enabled: Boolean(staffId),
    retry: false,
  });
}

export function useLeaveTypes(includeInactive = false) {
  return useQuery({
    queryKey: ["staff", "leave-types", includeInactive],
    queryFn: () =>
      api.get<LeaveTypeList>(
        withQuery(`${STAFF}/leave-types`, {
          include_inactive: includeInactive ? "true" : undefined,
        }),
      ),
    retry: false,
  });
}

export function useLeaveBalances(staffId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["staff", "leave-balances", staffId],
    queryFn: () =>
      api.get<LeaveBalanceList>(
        withQuery(`${STAFF}/leave-balances`, { staff_id: staffId ?? undefined }),
      ),
    enabled: Boolean(staffId) && enabled,
    retry: false,
  });
}

export interface LeaveRequestFilters {
  staffId?: string;
  status?: string;
  fromDate?: string;
  toDate?: string;
}

export function useLeaveRequests(filters: LeaveRequestFilters, enabled = true) {
  return useQuery({
    queryKey: ["staff", "leave-requests", filters],
    queryFn: () =>
      api.get<LeaveRequestList>(
        withQuery(`${STAFF}/leave-requests`, {
          staff_id: filters.staffId,
          status: filters.status,
          from_date: filters.fromDate,
          to_date: filters.toDate,
        }),
      ),
    enabled,
    retry: false,
  });
}

export function useLeaveCalendar(
  fromDate: string,
  toDate: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["staff", "leave-calendar", fromDate, toDate],
    queryFn: () =>
      api.get<LeaveCalendar>(
        withQuery(`${STAFF}/leave-calendar`, {
          from_date: fromDate,
          to_date: toDate,
        }),
      ),
    enabled: enabled && Boolean(fromDate) && Boolean(toDate),
    retry: false,
  });
}

export function useStaffDocuments(staffId: string | null) {
  return useQuery({
    queryKey: ["staff", "documents", staffId],
    queryFn: () => api.get<DocumentList>(`${STAFF}/${staffId}/documents`),
    enabled: Boolean(staffId),
    retry: false,
  });
}

export function hasPermission(permissions: string[] | undefined, key: string): boolean {
  return Boolean(permissions?.includes("*") || permissions?.includes(key));
}
