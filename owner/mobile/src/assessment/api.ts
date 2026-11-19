import { authorizedJson } from "../session/session";
import type {
  AssessmentList,
  AssessmentSummary,
  ScoreBulkResult,
  ScoreInput,
  ScoreSheet,
  SubmissionList,
  WindowList,
} from "./types";

const ASSESSMENT = "/api/v1/assessment";

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const suffix = search.toString();
  return suffix ? `?${suffix}` : "";
}

export function listAssessments(
  instanceId: string,
  yearId: string,
  limit = 200,
): Promise<AssessmentList> {
  return authorizedJson<AssessmentList>(
    instanceId,
    `${ASSESSMENT}/assessments${query({ year_id: yearId, limit })}`,
  );
}

export function getAssessment(
  instanceId: string,
  assessmentId: string,
): Promise<AssessmentSummary> {
  return authorizedJson<AssessmentSummary>(
    instanceId,
    `${ASSESSMENT}/assessments/${assessmentId}`,
  );
}

export function getScoreSheet(
  instanceId: string,
  assessmentId: string,
): Promise<ScoreSheet> {
  return authorizedJson<ScoreSheet>(
    instanceId,
    `${ASSESSMENT}/assessments/${assessmentId}/scores`,
  );
}

export function saveScores(
  instanceId: string,
  assessmentId: string,
  items: ScoreInput[],
): Promise<ScoreBulkResult> {
  return authorizedJson<ScoreBulkResult>(
    instanceId,
    `${ASSESSMENT}/assessments/${assessmentId}/scores`,
    { method: "PUT", body: { items } },
  );
}

export function listWindows(
  instanceId: string,
  yearId: string,
  sectionId: string,
  limit = 100,
): Promise<WindowList> {
  return authorizedJson<WindowList>(
    instanceId,
    `${ASSESSMENT}/windows${query({ year_id: yearId, section_id: sectionId, limit })}`,
  );
}

export function listSubmissions(
  instanceId: string,
  filters: {
    year_id: string;
    term_id: string;
    section_id: string;
    subject_id: string;
  },
): Promise<SubmissionList> {
  return authorizedJson<SubmissionList>(
    instanceId,
    `${ASSESSMENT}/submissions${query({ ...filters, limit: 50 })}`,
  );
}
