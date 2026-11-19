import type { Layout } from "@erp/documents";
import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type {
  DocType,
  FieldsResponse,
  GenerationBatch,
  GenerationBatchList,
  GenerationStudentList,
  GenerationTargets,
  IssuedDocumentList,
  PreviewResponse,
  StarterList,
  StudentList,
  TemplateDetail,
  TemplateList,
  VersionDetail,
} from "./types";

export function useTemplates(docType: DocType | null, query: string) {
  const params = new URLSearchParams({ limit: "200" });
  if (docType) params.set("doc_type", docType);
  if (query.trim()) params.set("q", query.trim());
  return useQuery({
    queryKey: ["documents", "templates", docType, query],
    queryFn: () => api.get<TemplateList>(`/api/v1/documents/templates?${params.toString()}`),
  });
}

export function useTemplate(templateId: string | null) {
  return useQuery({
    queryKey: ["documents", "template", templateId],
    queryFn: () => api.get<TemplateDetail>(`/api/v1/documents/templates/${templateId}`),
    enabled: Boolean(templateId),
  });
}

export function useVersion(templateId: string | null, versionId: string | null) {
  return useQuery({
    queryKey: ["documents", "version", templateId, versionId],
    queryFn: () =>
      api.get<VersionDetail>(`/api/v1/documents/templates/${templateId}/versions/${versionId}`),
    enabled: Boolean(templateId && versionId),
  });
}

export function useFields(enabled = true) {
  return useQuery({
    queryKey: ["documents", "fields"],
    queryFn: () => api.get<FieldsResponse>("/api/v1/documents/fields"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useStarters(enabled = true) {
  return useQuery({
    queryKey: ["documents", "starters"],
    queryFn: () => api.get<StarterList>("/api/v1/documents/templates/starters"),
    enabled,
    staleTime: 10 * 60_000,
  });
}

export function usePreview(
  layout: Layout,
  mode: "sample" | "student",
  studentId: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["documents", "preview", mode, studentId, layout],
    queryFn: () =>
      api.post<PreviewResponse>("/api/v1/documents/preview", {
        layout,
        mode,
        student_id: mode === "student" ? studentId : null,
      }),
    enabled: enabled && (mode === "sample" || Boolean(studentId)),
    staleTime: 0,
  });
}

export function useStudents(query: string, enabled: boolean) {
  const params = new URLSearchParams({ limit: "25" });
  if (query.trim()) params.set("q", query.trim());
  return useQuery({
    queryKey: ["documents", "students", query],
    queryFn: () => api.get<StudentList>(`/api/v1/students?${params.toString()}`),
    enabled,
    staleTime: 60_000,
  });
}

export function useGenerationTargets(enabled: boolean) {
  return useQuery({
    queryKey: ["documents", "generation", "targets"],
    queryFn: () => api.get<GenerationTargets>("/api/v1/documents/generation/targets"),
    enabled,
    staleTime: 60_000,
  });
}

export function useGenerationStudents(query: string, enabled: boolean) {
  const params = new URLSearchParams({ limit: "25" });
  if (query.trim()) params.set("q", query.trim());
  return useQuery({
    queryKey: ["documents", "generation", "students", query],
    queryFn: () =>
      api.get<GenerationStudentList>(
        `/api/v1/documents/generation/students?${params.toString()}`,
      ),
    enabled,
    staleTime: 30_000,
  });
}

export function useBatch(batchId: string | null) {
  return useQuery({
    queryKey: ["documents", "generation", "batch", batchId],
    queryFn: () => api.get<GenerationBatch>(`/api/v1/documents/generation/batches/${batchId}`),
    enabled: Boolean(batchId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1500 : false;
    },
  });
}

export function useBatches(templateId: string | null, enabled: boolean) {
  const params = new URLSearchParams({ limit: "10" });
  if (templateId) params.set("template_id", templateId);
  return useQuery({
    queryKey: ["documents", "generation", "batches", templateId],
    queryFn: () =>
      api.get<GenerationBatchList>(
        `/api/v1/documents/generation/batches?${params.toString()}`,
      ),
    enabled,
    staleTime: 15_000,
  });
}

export function useIssuedDocuments(query: string, templateId: string | null) {
  const params = new URLSearchParams({ limit: "50", sort: "issued_at", order: "desc" });
  if (query.trim()) params.set("q", query.trim());
  if (templateId) params.set("template_id", templateId);
  return useQuery({
    queryKey: ["documents", "issued", query, templateId],
    queryFn: () => api.get<IssuedDocumentList>(`/api/v1/documents/issued?${params.toString()}`),
    staleTime: 15_000,
  });
}
