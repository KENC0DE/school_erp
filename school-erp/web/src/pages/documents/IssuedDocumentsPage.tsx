import { ApiRequestError } from "@erp/api-client";
import { formatDual } from "@erp/calendar";
import {
  Button,
  EmptyState,
  ErrorState,
  Input,
  LoadingState,
  Page,
  PageHeader,
} from "@erp/ui-web";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { useIssuedDocuments } from "./queries";
import type { IssuedDocument, ReprintResult } from "./types";

function triggerDownload(url: string, filename?: string | null) {
  const anchor = document.createElement("a");
  anchor.href = url;
  if (filename) anchor.download = filename;
  anchor.target = "_blank";
  anchor.rel = "noreferrer";
  anchor.click();
}

export function IssuedDocumentsPage() {
  const { t, locale } = useI18n();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const issued = useIssuedDocuments(deferredSearch, null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reprint = async (document: IssuedDocument) => {
    setBusy(document.id);
    setError(null);
    setNotice(null);
    try {
      const result = await api.get<ReprintResult>(
        `/api/v1/documents/issued/${document.id}/reprint`,
      );
      if (!result.url) throw new Error("missing url");
      triggerDownload(result.url, `${result.number}.pdf`);
      setNotice(t("documents.issued.reprinted", { number: document.number }));
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("documents.issued.reprint_error"));
    } finally {
      setBusy(null);
    }
  };

  const items = issued.data?.items ?? [];

  return (
    <Page>
      <div className="space-y-5" data-testid="issued-page">
        <PageHeader
          title={t("documents.issued.title")}
          description={t("documents.issued.intro")}
          actions={
            <Link className="ui-btn ui-btn--outline ui-btn--sm" to="/documents">
              {t("documents.issued.back")}
            </Link>
          }
        />

        <div className="ui-table-toolbar">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("documents.issued.search")}
            aria-label={t("documents.issued.search")}
            data-testid="issued-search"
          />
        </div>

        {notice ? (
          <p role="status" className="text-sm text-muted-foreground" data-testid="issued-notice">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-destructive" data-testid="issued-error">
            {error}
          </p>
        ) : null}

        {issued.isPending ? (
          <LoadingState label={t("documents.issued.loading")} testId="issued-loading" />
        ) : issued.isError ? (
          <ErrorState
            title={t("documents.issued.error")}
            requestId={requestIdOf(issued.error)}
            retry={
              <Button variant="outline" onClick={() => void issued.refetch()}>
                {t("documents.issued.retry")}
              </Button>
            }
          />
        ) : items.length === 0 ? (
          <EmptyState
            title={t("documents.issued.empty_title")}
            description={t("documents.issued.empty_description")}
            action={
              <Link className="ui-btn ui-btn--primary ui-btn--sm" to="/documents">
                {t("documents.issued.back")}
              </Link>
            }
            testId="issued-empty"
          />
        ) : (
          <div className="ui-table-wrap">
            <table className="ui-table" data-testid="issued-list">
              <thead>
                <tr>
                  <th scope="col">{t("documents.issued.number")}</th>
                  <th scope="col">{t("documents.issued.recipient")}</th>
                  <th scope="col">{t("documents.issued.template")}</th>
                  <th scope="col">{t("documents.issued.issued_at")}</th>
                  <th scope="col">{t("documents.issued.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((document) => (
                  <tr key={document.id} data-testid={`issued-row-${document.number}`}>
                    <td className="ui-num">{document.number}</td>
                    <td>{document.recipient_name}</td>
                    <td>
                      <div>{document.template_name}</div>
                      <span className="text-xs text-muted-foreground">
                        {t("documents.issued.version", {
                          number: document.template_version_number,
                        })}
                      </span>
                    </td>
                    <td className="ui-num">
                      {formatDual(new Date(document.issued_at), "both", locale === "am" ? "am" : "en")}
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-2">
                        {document.download_url ? (
                          <Button
                            variant="outline"
                            size="sm"
                            data-testid={`issued-download-${document.number}`}
                            onClick={() =>
                              triggerDownload(
                                document.download_url as string,
                                `${document.number}.pdf`,
                              )
                            }
                          >
                            {t("documents.issued.download")}
                          </Button>
                        ) : null}
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy === document.id}
                          data-testid={`issued-reprint-${document.number}`}
                          onClick={() => void reprint(document)}
                        >
                          {busy === document.id
                            ? t("documents.issued.reprinting")
                            : t("documents.issued.reprint")}
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
    </Page>
  );
}
