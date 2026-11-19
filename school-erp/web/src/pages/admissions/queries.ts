import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import { withQuery } from "../students/queries";
import type {
  AdmissionForm,
  ApplicationDetail,
  ApplicationFilters,
  ApplicationList,
  ConversionPreview,
  PublicForm,
} from "./types";

export const ADMISSIONS = "/api/v1/admissions";

function filterParams(filters: ApplicationFilters): Record<string, string> {
  return {
    q: filters.q.trim(),
    status: filters.status,
    year_id: filters.year_id,
    level_id: filters.level_id,
  };
}

export function useAdmissions(filters: ApplicationFilters) {
  return useQuery({
    queryKey: ["admissions", "list", filters],
    queryFn: () => api.get<ApplicationList>(withQuery(ADMISSIONS, filterParams(filters))),
    retry: false,
  });
}

export function useApplication(applicationId: string | null) {
  return useQuery({
    queryKey: ["admissions", "detail", applicationId],
    queryFn: () => api.get<ApplicationDetail>(`${ADMISSIONS}/${applicationId}`),
    enabled: Boolean(applicationId),
    retry: false,
  });
}

export function useAdmissionForm() {
  return useQuery({
    queryKey: ["admissions", "form"],
    queryFn: () => api.get<AdmissionForm>(`${ADMISSIONS}/form`),
    retry: false,
  });
}

export function useConversionPreview(applicationId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["admissions", "conversion", applicationId],
    queryFn: () => api.get<ConversionPreview>(`${ADMISSIONS}/${applicationId}/conversion`),
    enabled: Boolean(applicationId) && enabled,
    retry: false,
  });
}

export function usePublicForm() {
  return useQuery({
    queryKey: ["admissions", "public", "form"],
    queryFn: () => api.get<PublicForm>(`${ADMISSIONS}/public/form`),
    retry: false,
  });
}
