import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { api } from "../lib/api";
import { useI18n } from "../providers/I18nProvider";

type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface JobRow {
  id: string;
  kind: string;
  status: JobStatus;
  progress: number;
  error_key: string | null;
  retryable: boolean;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

interface JobsResponse {
  items: JobRow[];
  next_cursor: string | null;
}

const STATUSES: JobStatus[] = ["queued", "running", "succeeded", "failed", "cancelled"];
const KNOWN_KINDS = ["ping", "files.thumbnail", "notifications.delivery"];
const ACTIVE: JobStatus[] = ["queued", "running"];

function formatDate(value: string | null, locale: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function kindKey(kind: string): string {
  return KNOWN_KINDS.includes(kind) ? `jobs.kind.${kind.replaceAll(".", "_")}` : "jobs.kind.other";
}

function progressValue(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function JobsPage() {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const jobs = useQuery({
    queryKey: ["jobs", status, kind],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (kind) params.set("kind", kind);
      const query = params.toString();
      return api.get<JobsResponse>(`/api/v1/jobs${query ? `?${query}` : ""}`);
    },
    // Keep progress moving while work is in flight, but never poll a quiet page.
    refetchInterval: (query) => {
      const data = query.state.data as JobsResponse | undefined;
      return data?.items.some((job) => ACTIVE.includes(job.status)) ? 5_000 : false;
    },
  });

  const retry = useMutation({
    mutationFn: (id: string) => api.post<JobRow>(`/api/v1/jobs/${id}/retry`),
    onSuccess: () => {
      setError(null);
      setNotice(t("jobs.retried"));
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (reason) => {
      setNotice(null);
      setError(reason instanceof ApiRequestError ? reason.message : t("common.error"));
    },
  });

  const items = jobs.data?.items ?? [];

  return (
    <div className="space-y-5" data-testid="jobs-page">
      <div>
        <h1 className="text-2xl font-semibold">{t("jobs.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("jobs.intro")}</p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1.5 text-sm font-medium">
          <span className="block">{t("jobs.status_filter")}</span>
          <select
            aria-label={t("jobs.status_filter")}
            className="h-10 min-w-40 rounded-md border border-input bg-background px-2 text-sm"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">{t("jobs.all_statuses")}</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {t(`jobs.status.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-sm font-medium">
          <span className="block">{t("jobs.kind_filter")}</span>
          <select
            aria-label={t("jobs.kind_filter")}
            className="h-10 min-w-48 rounded-md border border-input bg-background px-2 text-sm"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            <option value="">{t("jobs.all_kinds")}</option>
            {KNOWN_KINDS.map((value) => (
              <option key={value} value={value}>
                {t(kindKey(value))}
              </option>
            ))}
          </select>
        </label>
      </div>

      {notice ? (
        <p role="status" className="text-sm text-primary">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {jobs.isLoading ? (
        <p className="text-sm text-muted-foreground">{t("jobs.loading")}</p>
      ) : null}

      {!jobs.isLoading && items.length === 0 ? (
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-muted-foreground">{t("jobs.empty")}</p>
          </CardContent>
        </Card>
      ) : null}

      {items.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full border-collapse text-sm">
            <thead className="bg-secondary text-secondary-foreground">
              <tr>
                <th className="px-3 py-2 text-start font-medium">{t("jobs.col_kind")}</th>
                <th className="px-3 py-2 text-start font-medium">{t("jobs.col_status")}</th>
                <th className="px-3 py-2 text-start font-medium">{t("jobs.col_progress")}</th>
                <th className="px-3 py-2 text-start font-medium">{t("jobs.col_created")}</th>
                <th className="px-3 py-2 text-start font-medium">{t("jobs.col_actions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((job) => {
                const percent = progressValue(job.progress);
                return (
                  <tr
                    key={job.id}
                    className="border-t border-border align-top"
                    data-testid={`job-${job.id}`}
                  >
                    <td className="px-3 py-3">
                      <div className="font-medium">{t(kindKey(job.kind))}</div>
                      <div className="text-xs text-muted-foreground">{job.kind}</div>
                    </td>
                    <td className="px-3 py-3">
                      <Badge className={job.status === "failed" ? "text-destructive" : undefined}>
                        {t(`jobs.status.${job.status}`)}
                      </Badge>
                      {job.error_key ? (
                        <p role="alert" className="mt-1 max-w-md text-xs text-destructive">
                          {t(job.error_key)}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-2 w-32 overflow-hidden rounded-full bg-secondary"
                          role="progressbar"
                          aria-label={`${t(kindKey(job.kind))} ${t("jobs.col_progress")}`}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={percent}
                        >
                          <div
                            className="h-full bg-primary transition-all"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {t("jobs.progress", { percent })}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-muted-foreground">
                      {formatDate(job.created_at, locale)}
                    </td>
                    <td className="px-3 py-3">
                      {job.retryable ? (
                        <Button
                          variant="outline"
                          disabled={retry.isPending && retry.variables === job.id}
                          onClick={() => retry.mutate(job.id)}
                        >
                          {retry.isPending && retry.variables === job.id
                            ? t("jobs.retrying")
                            : t("jobs.retry")}
                        </Button>
                      ) : job.status === "failed" ? (
                        <span className="text-xs text-muted-foreground">
                          {t("jobs.retry_unavailable")}
                        </span>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
