import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type { StudentFilters, StudentList, StudentPhoto, StudentDetail } from "./types";

export const STUDENTS = "/api/v1/students";
export const ACADEMICS = "/api/v1/academics";

export function withQuery(path: string, params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

function filterParams(filters: StudentFilters, cursor?: string | null): Record<string, string> {
  return {
    q: filters.q.trim(),
    status: filters.status,
    year_id: filters.year_id,
    level_id: filters.level_id,
    section_id: filters.section_id,
    ...(cursor ? { cursor } : {}),
  };
}

export function useStudents(filters: StudentFilters, cursor: string | null) {
  return useQuery({
    queryKey: ["students", "list", filters, cursor],
    queryFn: () => api.get<StudentList>(withQuery(STUDENTS, filterParams(filters, cursor))),
    retry: false,
  });
}

export function useStudent(studentId: string | null) {
  return useQuery({
    queryKey: ["students", "detail", studentId],
    queryFn: () => api.get<StudentDetail>(`${STUDENTS}/${studentId}`),
    enabled: Boolean(studentId),
    retry: false,
  });
}

export function useStudentPhoto(studentId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["students", "photo", studentId],
    queryFn: () => api.get<StudentPhoto>(`${STUDENTS}/${studentId}/photo`),
    enabled: Boolean(studentId) && enabled,
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export interface AcademicYear {
  id: string;
  code: string;
  name: string;
  status: string;
}

export interface YearList {
  items: AcademicYear[];
  total: number;
  current_year_id: string | null;
}

export interface AcademicLevel {
  id: string;
  code: string;
  name: string;
  scope_level: number;
  in_scope: boolean;
}

export interface LevelList {
  items: AcademicLevel[];
  total: number;
}

export interface AcademicSection {
  id: string;
  year_id: string;
  level_id: string;
  code: string;
  name: string | null;
  is_active: boolean;
}

export interface SectionList {
  items: AcademicSection[];
  total: number;
}

export function useYears() {
  return useQuery({
    queryKey: ["academics", "years"],
    queryFn: () => api.get<YearList>(`${ACADEMICS}/academic-years`),
    retry: false,
  });
}

export function useLevels() {
  return useQuery({
    queryKey: ["academics", "levels", "school"],
    queryFn: () => api.get<LevelList>(`${ACADEMICS}/levels`),
    retry: false,
  });
}

export function useSections(yearId: string, levelId: string) {
  return useQuery({
    queryKey: ["academics", "sections", yearId, levelId],
    queryFn: () =>
      api.get<SectionList>(
        withQuery(`${ACADEMICS}/sections`, {
          year_id: yearId,
          level_id: levelId,
        }),
      ),
    enabled: Boolean(yearId),
    retry: false,
  });
}

export function hasPermission(permissions: string[] | undefined, key: string): boolean {
  return Boolean(permissions?.includes("*") || permissions?.includes(key));
}
