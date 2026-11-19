import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type {
  DocType,
  FieldsResponse,
  StarterList,
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
