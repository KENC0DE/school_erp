import { useEffect, useState } from "react";

import { Button } from "../components/ui/Button";
import { Textarea } from "../components/ui/Textarea";
import { useT } from "../i18n";
import { api, API_PREFIX, supportSessionUrl } from "../lib/api";
import type { SupportSession } from "../lib/types";

interface Props {
  schoolId: string;
  schoolName: string;
  open: boolean;
  onClose: () => void;
}

const MIN_REASON = 4;
const MAX_REASON = 1000;

export function SupportSessionDialog({ schoolId, schoolName, open, onClose }: Props) {
  const t = useT();
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<SupportSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setReason("");
      setResult(null);
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  if (!open) return null;

  const trimmed = reason.trim();
  const tooShort = trimmed.length < MIN_REASON;
  const valid = !tooShort && trimmed.length <= MAX_REASON;

  const submit = async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const session = await api.post<SupportSession>(
        `${API_PREFIX}/schools/${schoolId}/support-session`,
        { reason: trimmed, read_only: false },
      );
      setResult(session);
      window.open(supportSessionUrl(session.token, trimmed), "_blank", "noopener,noreferrer");
    } catch (err) {
      const message = err instanceof Error && err.message ? err.message : t("controller.support.error");
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="support-session-title"
        data-testid="support-session-dialog"
        className="w-full max-w-lg rounded-lg border border-border bg-card p-5 text-card-foreground shadow-lg"
      >
        <h2 id="support-session-title" className="text-lg font-semibold">
          {t("controller.support.title")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("controller.support.description", { school: schoolName })}
        </p>

        {result ? (
          <div className="mt-4 flex flex-col gap-3">
            <p role="status" className="text-sm text-foreground">
              {t("controller.support.success")}
            </p>
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("controller.support.token")}
              </span>
              <code
                data-testid="support-token"
                className="break-all rounded-md border border-border bg-muted p-2 text-xs"
              >
                {result.token}
              </code>
            </div>
            <div className="text-sm">
              <span className="text-muted-foreground">{t("controller.support.expires")}: </span>
              <span data-testid="support-expires">
                {new Date(result.expires_at).toLocaleString()}
              </span>
            </div>
            <div className="flex justify-end">
              <Button onClick={onClose} data-testid="support-close">
                {t("controller.support.close")}
              </Button>
            </div>
          </div>
        ) : (
          <form
            className="mt-4 flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <div className="flex flex-col gap-1.5">
              <label htmlFor="support-reason" className="text-sm font-medium">
                {t("controller.support.reason")}
              </label>
              <Textarea
                id="support-reason"
                name="reason"
                value={reason}
                maxLength={MAX_REASON}
                aria-describedby="support-reason-hint"
                aria-invalid={reason.length > 0 && tooShort}
                autoFocus
                onChange={(event) => setReason(event.target.value)}
              />
              <p id="support-reason-hint" className="text-xs text-muted-foreground">
                {t("controller.support.reasonHint")}
              </p>
              {reason.length > 0 && tooShort ? (
                <p role="alert" className="text-xs text-destructive">
                  {t("controller.support.tooShort")}
                </p>
              ) : null}
            </div>
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={onClose} data-testid="support-cancel">
                {t("controller.support.cancel")}
              </Button>
              <Button type="submit" disabled={!valid || submitting} data-testid="support-submit">
                {t(submitting ? "controller.support.submitting" : "controller.support.submit")}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
