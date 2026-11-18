import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, EmptyState, ErrorState, LoadingState } from "@erp/ui-web";
import { useState, type ChangeEvent } from "react";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { STAFF, useStaffDocuments } from "./queries";
import type { UploadedStaffDocument } from "./types";

export function StaffDocuments({
  staffId,
  canManage,
}: {
  staffId: string;
  canManage: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const documents = useStaffDocuments(staffId);

  const remove = useMutation({
    mutationFn: (fileId: string) => api.del(`${STAFF}/${staffId}/documents/${fileId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["staff", "documents", staffId] });
    },
    onError: (caught) => {
      setError(caught instanceof ApiRequestError ? caught.message : t("staff.documents.failed"));
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
      await api.postForm<UploadedStaffDocument>(`${STAFF}/${staffId}/documents`, form);
      await queryClient.invalidateQueries({ queryKey: ["staff", "documents", staffId] });
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("staff.documents.failed"));
    } finally {
      setBusy(false);
    }
  }

  if (documents.isPending) {
    return <LoadingState label={t("common.loading")} testId="staff-documents-loading" />;
  }
  if (documents.isError) {
    return (
      <ErrorState
        title={t("staff.documents.load_error")}
        requestId={requestIdOf(documents.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button variant="outline" onClick={() => void documents.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );
  }

  const items = documents.data?.items ?? [];

  return (
    <div className="space-y-4" data-testid="staff-documents">
      {canManage ? (
        <label className="block space-y-1 text-sm">
          <span className="font-medium">{t("staff.documents.upload")}</span>
          <input
            type="file"
            disabled={busy}
            className="block text-sm text-muted-foreground"
            onChange={(event) => void upload(event)}
          />
        </label>
      ) : null}
      {busy ? <p className="text-sm text-muted-foreground">{t("staff.documents.uploading")}</p> : null}

      {items.length === 0 ? (
        <EmptyState title={t("staff.documents.empty")} />
      ) : (
        <ul className="space-y-2">
          {items.map((document) => (
            <li
              key={document.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
              data-testid={`staff-document-${document.id}`}
            >
              <a className="ui-link min-w-0" href={document.url} target="_blank" rel="noreferrer">
                {document.name}
              </a>
              <span className="text-xs text-muted-foreground">
                {t("staff.documents.size", {
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
                  {t("staff.documents.delete")}
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
