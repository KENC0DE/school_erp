import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, EmptyState, ErrorState, LoadingState } from "@erp/ui-web";
import { useState, type ChangeEvent } from "react";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { ADMISSIONS } from "./queries";
import type { ApplicationDetail, ApplicationDocument, ApplicationDocumentList } from "./types";

export function ApplicationDocuments({
  application,
  canManage,
}: {
  application: ApplicationDetail;
  canManage: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const documents = useQuery({
    queryKey: ["admissions", "documents", application.id],
    queryFn: () => api.get<ApplicationDocumentList>(`${ADMISSIONS}/${application.id}/documents`),
    retry: false,
  });

  const remove = useMutation({
    mutationFn: (fileId: string) => api.del(`${ADMISSIONS}/${application.id}/documents/${fileId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admissions", "documents", application.id] });
    },
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("admissions.documents.failed"));
    },
  });

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    try {
      await api.postForm<ApplicationDocument>(`${ADMISSIONS}/${application.id}/documents`, form);
      await queryClient.invalidateQueries({
        queryKey: ["admissions", "documents", application.id],
      });
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("admissions.documents.failed"));
    } finally {
      setBusy(false);
    }
  }

  if (documents.isPending) {
    return <LoadingState label={t("admissions.documents.loading")} testId="admission-documents-loading" />;
  }
  if (documents.isError) {
    return (
      <ErrorState
        title={t("admissions.documents.load_error")}
        requestId={requestIdOf(documents.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button variant="outline" onClick={() => void documents.refetch()}>
            {t("common.retry")}
          </Button>
        }
        testId="admission-documents-error"
      />
    );
  }

  const items = documents.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="admission-documents">
      {canManage ? (
        <label className="block space-y-1 text-sm">
          <span className="font-medium">{t("admissions.documents.upload")}</span>
          <input
            type="file"
            disabled={busy}
            className="block text-sm text-muted-foreground"
            data-testid="admission-document-upload"
            onChange={(event) => void upload(event)}
          />
        </label>
      ) : null}
      {busy ? <p className="text-sm text-muted-foreground">{t("files.uploading")}</p> : null}

      {items.length === 0 ? (
        <EmptyState title={t("admissions.documents.empty")} testId="admission-documents-empty" />
      ) : (
        <ul className="space-y-2">
          {items.map((document) => (
            <li
              key={document.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
              data-testid={`admission-document-${document.id}`}
            >
              <a className="ui-link min-w-0" href={document.url} target="_blank" rel="noreferrer">
                {document.name}
              </a>
              <span className="text-xs text-muted-foreground">
                {t("admissions.documents.size", {
                  kb: Math.max(1, Math.round(document.size_bytes / 1024)),
                })}
              </span>
              {canManage ? (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(document.id)}
                >
                  {t("admissions.documents.delete")}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
