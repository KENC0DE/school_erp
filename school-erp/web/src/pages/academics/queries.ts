import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type {
  CurriculumProfileList,
  LevelList,
  LevelSubjects,
  SectionList,
  SubjectGroupList,
  SubjectList,
  UserList,
  YearList,
} from "./types";

export const ACADEMICS = "/api/v1/academics";

function withQuery(path: string, params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export function useScope() {
  return useQuery({
    queryKey: ["academics", "scope"],
    queryFn: () => api.get<LevelList["scope"]>(`${ACADEMICS}/scope`),
  });
}

export function useLevels(allScope: boolean) {
  return useQuery({
    queryKey: ["academics", "levels", allScope],
    queryFn: () => api.get<LevelList>(withQuery(`${ACADEMICS}/levels`, { scope: allScope ? "all" : undefined })),
  });
}

export function useYears() {
  return useQuery({
    queryKey: ["academics", "years"],
    queryFn: () => api.get<YearList>(`${ACADEMICS}/academic-years`),
  });
}

export function useProfiles() {
  return useQuery({
    queryKey: ["academics", "profiles"],
    queryFn: () => api.get<CurriculumProfileList>(`${ACADEMICS}/curriculum-profiles`),
  });
}

export function useSubjects() {
  return useQuery({
    queryKey: ["academics", "subjects"],
    queryFn: () => api.get<SubjectList>(`${ACADEMICS}/subjects`),
  });
}

export function useGroups() {
  return useQuery({
    queryKey: ["academics", "groups"],
    queryFn: () => api.get<SubjectGroupList>(`${ACADEMICS}/subject-groups`),
  });
}

export function useLevelSubjects(levelId: string | null) {
  return useQuery({
    queryKey: ["academics", "level-subjects", levelId],
    queryFn: () => api.get<LevelSubjects>(`${ACADEMICS}/levels/${levelId}/subjects`),
    enabled: Boolean(levelId),
  });
}

export function useSections(yearId: string | null) {
  return useQuery({
    queryKey: ["academics", "sections", yearId],
    queryFn: () => api.get<SectionList>(withQuery(`${ACADEMICS}/sections`, { year_id: yearId ?? undefined })),
  });
}

export function useHomeroomUsers(enabled: boolean) {
  return useQuery({
    queryKey: ["academics", "homeroom-users"],
    queryFn: () => api.get<UserList>("/api/v1/auth/users"),
    enabled,
  });
}

export function can(permissions: string[], key: string): boolean {
  return permissions.includes("*") || permissions.includes(key);
}
