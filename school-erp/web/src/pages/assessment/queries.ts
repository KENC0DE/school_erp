import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type { LevelList, SubjectList, YearList } from "../academics/types";
import type {
  AssessmentSummaryList,
  GradeScaleList,
  ScaleAssignmentList,
  StageList,
  StructureList,
} from "./types";

export const ASSESSMENT = "/api/v1/assessment";
export const ACADEMICS = "/api/v1/academics";

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

export function useStructures(yearId: string | null) {
  return useQuery({
    queryKey: ["assessment", "structures", yearId],
    queryFn: () =>
      api.get<StructureList>(
        withQuery(`${ASSESSMENT}/structures`, { year_id: yearId ?? undefined, limit: 200 }),
      ),
    enabled: Boolean(yearId),
    retry: false,
  });
}

export function useAssessmentYears() {
  return useQuery({
    queryKey: ["assessment", "years"],
    queryFn: () => api.get<YearList>(`${ACADEMICS}/academic-years`),
    retry: false,
  });
}

export function useAssessmentLevels(enabled: boolean) {
  return useQuery({
    queryKey: ["assessment", "levels"],
    queryFn: () => api.get<LevelList>(`${ACADEMICS}/levels`),
    enabled,
    retry: false,
  });
}

export function useAssessmentStages(enabled: boolean) {
  return useQuery({
    queryKey: ["assessment", "stages"],
    queryFn: () => api.get<StageList>(`${ACADEMICS}/stages`),
    enabled,
    retry: false,
  });
}

export function useAssessmentSubjects(enabled: boolean) {
  return useQuery({
    queryKey: ["assessment", "subjects"],
    queryFn: () => api.get<SubjectList>(`${ACADEMICS}/subjects`),
    enabled,
    retry: false,
  });
}

export function useScales() {
  return useQuery({
    queryKey: ["assessment", "scales"],
    queryFn: () => api.get<GradeScaleList>(`${ASSESSMENT}/scales`),
    retry: false,
  });
}

export function useScaleAssignments() {
  return useQuery({
    queryKey: ["assessment", "scale-assignments"],
    queryFn: () => api.get<ScaleAssignmentList>(`${ASSESSMENT}/scale-assignments`),
    retry: false,
  });
}

export function useScaleAssessments(yearId: string | null) {
  return useQuery({
    queryKey: ["assessment", "assessments", yearId],
    queryFn: () =>
      api.get<AssessmentSummaryList>(
        withQuery(`${ASSESSMENT}/assessments`, { year_id: yearId ?? undefined, limit: 200 }),
      ),
    enabled: Boolean(yearId),
    retry: false,
  });
}
