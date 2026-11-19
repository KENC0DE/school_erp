import { authorizedJson } from "../session/session";
import type {
  LevelList,
  RegistrationPreview,
  SectionList,
  StudentDetail,
  StudentFilters,
  StudentList,
  StudentRegistration,
  StudentSummary,
  YearList,
} from "./types";

const STUDENTS = "/api/v1/students";
const ACADEMICS = "/api/v1/academics";

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const suffix = search.toString();
  return suffix ? `?${suffix}` : "";
}

export function listStudents(
  instanceId: string,
  filters: StudentFilters,
  cursor?: string | null,
): Promise<StudentList> {
  return authorizedJson<StudentList>(
    instanceId,
    `${STUDENTS}${query({ q: filters.q?.trim(), status: filters.status, cursor: cursor ?? undefined, limit: 25 })}`,
  );
}

export function getStudent(instanceId: string, studentId: string): Promise<StudentDetail> {
  return authorizedJson<StudentDetail>(instanceId, `${STUDENTS}/${studentId}`);
}

export function previewRegistration(
  instanceId: string,
  data: StudentRegistration,
): Promise<RegistrationPreview> {
  return authorizedJson<RegistrationPreview>(instanceId, `${STUDENTS}/register/preview`, {
    method: "POST",
    body: data,
  });
}

export function registerStudent(
  instanceId: string,
  data: StudentRegistration,
): Promise<StudentSummary> {
  return authorizedJson<StudentSummary>(instanceId, STUDENTS, {
    method: "POST",
    body: data,
  });
}

export function listYears(instanceId: string): Promise<YearList> {
  return authorizedJson<YearList>(instanceId, `${ACADEMICS}/academic-years`);
}

export function listLevels(instanceId: string): Promise<LevelList> {
  return authorizedJson<LevelList>(instanceId, `${ACADEMICS}/levels`);
}

export function listSections(
  instanceId: string,
  yearId: string,
  levelId: string,
): Promise<SectionList> {
  return authorizedJson<SectionList>(
    instanceId,
    `${ACADEMICS}/sections${query({ year_id: yearId, level_id: levelId })}`,
  );
}
