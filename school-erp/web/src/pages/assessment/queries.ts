import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type { LevelList, SubjectList, YearList } from "../academics/types";
import type {
  AssessmentList,
  AssessmentSummaryList,
  DashboardOut,
  GradeScaleList,
  MarkingWindowList,
  PortalResults,
  ScaleAssignmentList,
  ScoreSheet,
  StageList,
  StructureList,
  SubmissionList,
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
        withQuery(`${ASSESSMENT}/structures`, {
          year_id: yearId ?? undefined,
          limit: 200,
        }),
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
    queryFn: () =>
      api.get<ScaleAssignmentList>(`${ASSESSMENT}/scale-assignments`),
    retry: false,
  });
}

export function useScaleAssessments(yearId: string | null) {
  return useQuery({
    queryKey: ["assessment", "assessments", yearId],
    queryFn: () =>
      api.get<AssessmentSummaryList>(
        withQuery(`${ASSESSMENT}/assessments`, {
          year_id: yearId ?? undefined,
          limit: 200,
        }),
      ),
    enabled: Boolean(yearId),
    retry: false,
  });
}

export function useMarkAssessments(yearId: string | null) {
  return useQuery({
    queryKey: ["assessment", "mark-assessments", yearId],
    queryFn: () =>
      api.get<AssessmentList>(
        withQuery(`${ASSESSMENT}/assessments`, {
          year_id: yearId ?? undefined,
          limit: 200,
        }),
      ),
    enabled: Boolean(yearId),
    retry: false,
  });
}

export function useMarkSheets(assessmentIds: string[]) {
  return useQuery({
    queryKey: ["assessment", "mark-sheets", assessmentIds],
    queryFn: () =>
      Promise.all(
        assessmentIds.map((id) =>
          api.get<ScoreSheet>(`${ASSESSMENT}/assessments/${id}/scores`),
        ),
      ),
    enabled: assessmentIds.length > 0,
    retry: false,
  });
}

export function useMarkWindows(
  yearId: string | null,
  sectionId: string | null,
) {
  return useQuery({
    queryKey: ["assessment", "mark-windows", yearId, sectionId],
    queryFn: () =>
      api.get<MarkingWindowList>(
        withQuery(`${ASSESSMENT}/windows`, {
          year_id: yearId ?? undefined,
          section_id: sectionId ?? undefined,
          limit: 200,
        }),
      ),
    enabled: Boolean(yearId && sectionId),
    retry: false,
  });
}

export function useMarkSubmission(
  yearId: string | null,
  sectionId: string | null,
  subjectId: string | null,
) {
  return useQuery({
    queryKey: ["assessment", "mark-submission", yearId, sectionId, subjectId],
    queryFn: () =>
      api.get<SubmissionList>(
        withQuery(`${ASSESSMENT}/submissions`, {
          year_id: yearId ?? undefined,
          section_id: sectionId ?? undefined,
          subject_id: subjectId ?? undefined,
          limit: 10,
        }),
      ),
    enabled: Boolean(yearId && sectionId && subjectId),
    retry: false,
  });
}

export function useAssessmentDashboard(
  yearId: string | null,
  termId: string | null,
  sectionId?: string | null,
  subjectId?: string | null,
) {
  return useQuery({
    queryKey: ["assessment", "dashboard", yearId, termId, sectionId, subjectId],
    queryFn: () =>
      api.get<DashboardOut>(
        withQuery(`${ASSESSMENT}/dashboard`, {
          year_id: yearId ?? undefined,
          term_id: termId ?? undefined,
          section_id: sectionId ?? undefined,
          subject_id: subjectId ?? undefined,
        }),
      ),
    enabled: Boolean(yearId && termId),
    retry: false,
  });
}

export function useApprovalSubmissions(
  yearId: string | null,
  termId: string | null,
  status: string,
) {
  return useQuery({
    queryKey: ["assessment", "approval-submissions", yearId, termId, status],
    queryFn: () =>
      api.get<SubmissionList>(
        withQuery(`${ASSESSMENT}/submissions`, {
          year_id: yearId ?? undefined,
          term_id: termId ?? undefined,
          status: status === "all" ? undefined : status,
          limit: 200,
        }),
      ),
    enabled: Boolean(yearId && termId),
    retry: false,
  });
}

export function useApprovalAssessments(
  yearId: string | null,
  termId: string | null,
  sectionId: string | null,
  subjectId: string | null,
) {
  return useQuery({
    queryKey: [
      "assessment",
      "approval-assessments",
      yearId,
      termId,
      sectionId,
      subjectId,
    ],
    queryFn: () =>
      api.get<AssessmentList>(
        withQuery(`${ASSESSMENT}/assessments`, {
          year_id: yearId ?? undefined,
          term_id: termId ?? undefined,
          section_id: sectionId ?? undefined,
          subject_id: subjectId ?? undefined,
          limit: 200,
        }),
      ),
    enabled: Boolean(yearId && termId && sectionId && subjectId),
    retry: false,
  });
}

export function usePortalResults(yearId: string | null) {
  return useQuery({
    queryKey: ["assessment", "portal-results", yearId],
    queryFn: () =>
      api.get<PortalResults>(
        withQuery(`${ASSESSMENT}/portal/results`, {
          year_id: yearId ?? undefined,
        }),
      ),
    retry: false,
  });
}
