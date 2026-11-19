import { ApiRequestError } from "@erp/api-client";
import { formatDual } from "@erp/calendar";
import {
  Badge,
  Button,
  Card,
  CardContent,
  ErrorState,
  LoadingState,
} from "@erp/ui-web";
import { useParams } from "react-router-dom";

import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { useDocumentVerification } from "./queries";

/**
 * The public page behind the QR code printed on an issued document.
 *
 * It sits outside the authenticated shell so a guardian can scan a paper
 * certificate without an account. The API returns only the minimal facts, so
 * this page cannot be used to read the snapshot behind the document.
 */
export function VerifyDocumentPage() {
  const { code = "" } = useParams<{ code: string }>();
  const { t, locale } = useI18n();
  const verification = useDocumentVerification(code);
  const missing =
    verification.error instanceof ApiRequestError && verification.error.status === 404;
  const document = verification.data;

  return (
    <main className="mx-auto max-w-xl space-y-5 p-6" data-testid="verify-page">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold">
          {document?.school_name || t("documents.verify.title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("documents.verify.intro")}</p>
      </header>

      <Card>
        <CardContent className="p-6">
          {verification.isPending ? (
            <LoadingState label={t("documents.verify.loading")} testId="verify-loading" />
          ) : missing ? (
            <ErrorState
              title={t("documents.verify.invalid_title")}
              description={t("documents.verify.invalid_description")}
              testId="verify-invalid"
            />
          ) : verification.isError && !document ? (
            <ErrorState
              title={t("documents.verify.error_title")}
              description={t("documents.verify.error_description")}
              requestId={requestIdOf(verification.error)}
              requestIdLabel={t("common.request_id")}
              retry={
                <Button variant="outline" onClick={() => void verification.refetch()}>
                  {t("documents.verify.retry")}
                </Button>
              }
              testId="verify-error"
            />
          ) : document ? (
            <div className="space-y-4" data-testid="verify-valid">
              <Badge variant="success">{t("documents.verify.valid")}</Badge>
              <p className="text-sm text-muted-foreground">{t("documents.verify.valid_hint")}</p>
              <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-3 text-sm">
                <dt className="text-muted-foreground">{t("documents.verify.number")}</dt>
                <dd className="font-medium" data-testid="verify-number">
                  {document.number}
                </dd>
                <dt className="text-muted-foreground">{t("documents.verify.type")}</dt>
                <dd>{t(`documents.type.${document.doc_type}`)}</dd>
                <dt className="text-muted-foreground">{t("documents.verify.recipient")}</dt>
                <dd data-testid="verify-recipient">{document.recipient_name}</dd>
                <dt className="text-muted-foreground">{t("documents.verify.issued_at")}</dt>
                <dd>
                  {formatDual(
                    new Date(document.issued_at),
                    "both",
                    locale === "am" ? "am" : "en",
                  )}
                </dd>
              </dl>
              <p className="text-xs text-muted-foreground">{t("documents.verify.privacy")}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </main>
  );
}
