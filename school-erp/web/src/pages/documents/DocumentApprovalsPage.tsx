import { ApiRequestError } from "@erp/api-client";
import { formatDual } from "@erp/calendar";
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Page,
  PageHeader,
  Textarea,
} from "@erp/ui-web";
import { useState } from "react";
import { Link } from "react-router-dom";

import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import {
  useApprovalQueue,
  useApproveBatch,
  useRejectBatch,
} from "./queries";
import type { GenerationBatch } from "./types";

function shortId(id: string): string {
  return id.slice(0, 8).toUpperCase();
}

function readable(caught: unknown, fallback: string): string {
  return caught instanceof ApiRequestError ? caught.message : fallback;
}

export function DocumentApprovalsPage() {
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const allowed =
    (user?.permissions ?? []).includes("*") ||
    (user?.permissions ?? []).includes("documents.approve");
  const queue = useApprovalQueue(allowed);
  const approve = useApproveBatch();
  const reject = useRejectBatch();
  const [rejecting, setRejecting] = useState<GenerationBatch | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!allowed) {
    return (
      <Page>
        <PageHeader
          title={t("documents.approvals.title")}
          description={t("documents.approvals.intro")}
        />
        <p role="alert" className="text-sm text-destructive" data-testid="approvals-permission">
          {t("error.permission_denied")}
        </p>
      </Page>
    );
  }

  const items = queue.data?.items ?? [];

  const approveNow = async (batch: GenerationBatch) => {
    setError(null);
    setNotice(null);
    try {
      await approve.mutateAsync({ batchId: batch.id });
      setNotice(t("documents.approvals.approved"));
    } catch (caught) {
      setError(readable(caught, t("documents.approvals.approve_error")));
    }
  };

  const openReject = (batch: GenerationBatch) => {
    setRejecting(batch);
    setReason("");
    setReasonError(null);
  };

  const closeReject = () => {
    setRejecting(null);
    setReason("");
    setReasonError(null);
  };

  const confirmReject = async () => {
    if (!rejecting) return;
    if (reason.trim().length < 3) {
      setReasonError(t("documents.approvals.reason_required"));
      return;
    }
    setError(null);
    setNotice(null);
    try {
      await reject.mutateAsync({ batchId: rejecting.id, reason: reason.trim() });
      setNotice(t("documents.approvals.rejected"));
      closeReject();
    } catch (caught) {
      setError(readable(caught, t("documents.approvals.reject_error")));
    }
  };

  return (
    <Page>
      <div className="space-y-5" data-testid="approvals-page">
        <PageHeader
          title={t("documents.approvals.title")}
          description={t("documents.approvals.intro")}
          actions={
            <Link className="ui-btn ui-btn--outline ui-btn--sm" to="/">
              {t("nav.dashboard")}
            </Link>
          }
        />

        {notice ? (
          <p role="status" className="text-sm text-muted-foreground" data-testid="approvals-notice">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-destructive" data-testid="approvals-error">
            {error}
          </p>
        ) : null}

        {queue.isPending ? (
          <LoadingState
            label={t("documents.approvals.loading")}
            testId="approvals-loading"
          />
        ) : queue.isError ? (
          <ErrorState
            title={t("documents.approvals.error")}
            requestId={requestIdOf(queue.error)}
            retry={
              <Button variant="outline" onClick={() => void queue.refetch()}>
                {t("documents.approvals.retry")}
              </Button>
            }
          />
        ) : items.length === 0 ? (
          <EmptyState
            title={t("documents.approvals.empty_title")}
            description={t("documents.approvals.empty_description")}
            action={
              <Link className="ui-btn ui-btn--primary ui-btn--sm" to="/">
                {t("nav.dashboard")}
              </Link>
            }
            testId="approvals-empty"
          />
        ) : (
          <div className="ui-table-wrap">
            <table className="ui-table" data-testid="approvals-list">
              <thead>
                <tr>
                  <th scope="col">{t("documents.generation.template")}</th>
                  <th scope="col">{t("documents.approvals.requester")}</th>
                  <th scope="col">{t("documents.approvals.documents")}</th>
                  <th scope="col">{t("documents.issued.issued_at")}</th>
                  <th scope="col">{t("documents.issued.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((batch) => (
                  <tr key={batch.id} data-testid={`approval-row-${batch.id}`}>
                    <td>
                      <div>{batch.template_name}</div>
                      <span className="text-xs text-muted-foreground">
                        {t("documents.approvals.batch", { id: shortId(batch.id) })} ·{" "}
                        {t("documents.approvals.version", {
                          number: batch.template_version_number,
                        })}
                      </span>
                    </td>
                    <td>
                      {batch.requested_by ? (
                        t("documents.approvals.requested_by", { name: batch.requested_by })
                      ) : (
                        t("documents.approvals.unknown_requester")
                      )}
                    </td>
                    <td className="ui-num">
                      {t("documents.approvals.count", { count: batch.count })}
                    </td>
                    <td className="ui-num">
                      {formatDual(
                        new Date(batch.created_at),
                        "both",
                        locale === "am" ? "am" : "en",
                      )}
                    </td>
                    <td>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="warning">{t("documents.approvals.pending")}</Badge>
                        <Button
                          size="sm"
                          data-testid={`approval-approve-${batch.id}`}
                          disabled={approve.isPending}
                          onClick={() => void approveNow(batch)}
                        >
                          {approve.isPending && approve.variables?.batchId === batch.id
                            ? t("documents.approvals.approving")
                            : t("documents.approvals.approve")}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          data-testid={`approval-reject-${batch.id}`}
                          disabled={reject.isPending}
                          onClick={() => openReject(batch)}
                        >
                          {t("documents.approvals.reject")}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog
        open={Boolean(rejecting)}
        onClose={closeReject}
        title={t("documents.approvals.reject_title")}
        description={t("documents.approvals.reject_description")}
        closeLabel={t("documents.approvals.cancel")}
        footer={
          <>
            <Button variant="outline" onClick={closeReject}>
              {t("documents.approvals.cancel")}
            </Button>
            <Button
              variant="destructive"
              data-testid="approvals-confirm-reject"
              disabled={reject.isPending}
              onClick={() => void confirmReject()}
            >
              {reject.isPending
                ? t("documents.approvals.rejecting")
                : t("documents.approvals.confirm_reject")}
            </Button>
          </>
        }
      >
        <Field
          label={t("documents.approvals.reason")}
          required
          error={reasonError ?? undefined}
        >
          <Textarea
            value={reason}
            data-testid="approvals-reason"
            placeholder={t("documents.approvals.reason_placeholder")}
            onChange={(event) => {
              setReason(event.target.value);
              if (reasonError) setReasonError(null);
            }}
          />
        </Field>
      </Dialog>
    </Page>
  );
}
