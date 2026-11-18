import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { EmptyState, ErrorState, LoadingState } from "@erp/ui-web";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { API_URL, api } from "../lib/api";
import { requestIdOf } from "../lib/errors";
import { getAccessToken } from "../lib/storage";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

export interface TranslationEntry {
  namespace: string;
  key: string;
  source: string;
  value: string;
  status: "approved" | "needs_review" | "missing";
  source_kind: string | null;
  layer: "default" | "central" | "school" | null;
  updated_at: string | null;
}

interface EntryList {
  items: TranslationEntry[];
  total: number;
  next_cursor: string | null;
}

interface TranslationStats {
  total: number;
  missing: number;
  needs_review: number;
  overrides: number;
}

interface Filters {
  locale: string;
  namespace: string;
  q: string;
  status: string;
  layer: string;
}

const DEFAULT_FILTERS: Filters = {
  locale: "am",
  namespace: "",
  q: "",
  status: "",
  layer: "",
};

const STATUS_LABEL: Record<string, string> = {
  approved: "translations.approved",
  needs_review: "translations.needs_review",
  missing: "translations.missing",
};

const LAYER_LABEL: Record<string, string> = {
  default: "translations.layer.default",
  central: "translations.layer.central",
  school: "translations.layer.school",
};

function hasPermission(permissions: string[] | undefined, permission: string): boolean {
  return Boolean(permissions?.includes("*") || permissions?.includes(permission));
}

function entryId(entry: Pick<TranslationEntry, "namespace" | "key">): string {
  return `${entry.namespace}:${entry.key}`;
}

function errorKey(error: unknown): string {
  if (error instanceof ApiRequestError && error.code === "PERMISSION_DENIED") {
    return "error.permission_denied";
  }
  return "common.error";
}

function EntryState({ entry }: { entry: TranslationEntry }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Badge data-testid={`translation-status-${entry.key}`}>
        {t(STATUS_LABEL[entry.status] ?? "translations.approved")}
      </Badge>
      {entry.layer ? (
        <Badge data-testid={`translation-layer-${entry.key}`}>{t(LAYER_LABEL[entry.layer])}</Badge>
      ) : null}
    </div>
  );
}

function EntryEditor({
  entry,
  locale,
  canManage,
  onSaved,
  testId = entry.key,
}: {
  entry: TranslationEntry;
  locale: string;
  canManage: boolean;
  onSaved?: () => void;
  testId?: string;
}) {
  const { t, reload } = useI18n();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(entry.value);
  const [status, setStatus] = useState(entry.status === "missing" ? "approved" : entry.status);
  const [aiNotice, setAiNotice] = useState<string | null>(null);

  useEffect(() => {
    setDraft(entry.value);
    setStatus(entry.status === "missing" ? "approved" : entry.status);
  }, [entry.value, entry.status, entry.key]);

  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: ["translations"] });
    await queryClient.invalidateQueries({ queryKey: ["translation-stats"] });
    reload();
    onSaved?.();
  };

  const save = useMutation({
    mutationFn: () =>
      api.put<TranslationEntry>(
        `/api/v1/i18n/editor/entries/${encodeURIComponent(entry.namespace)}/${encodeURIComponent(entry.key)}/${encodeURIComponent(locale)}`,
        { value: draft, status },
      ),
    onSuccess: done,
  });

  const suggest = useMutation({
    mutationFn: () =>
      api.post<{
        configured: boolean;
        status: string;
        message_key?: string;
        draft?: string;
        written?: boolean;
      }>("/api/v1/i18n/editor/suggest", {
        namespace: entry.namespace,
        key: entry.key,
        locale,
      }),
    onSuccess: async (result) => {
      if (!result.configured) {
        setAiNotice("translations.ai_not_configured");
        return;
      }
      if (result.draft) {
        setDraft(result.draft);
        setStatus("needs_review");
      }
      setAiNotice(result.written ? "translations.ai_written" : "translations.ai_existing");
      if (result.written) await done();
    },
    onError: () => setAiNotice("common.error"),
  });

  const reset = useMutation({
    mutationFn: () =>
      api.post<TranslationEntry>(
        `/api/v1/i18n/editor/entries/${encodeURIComponent(entry.namespace)}/${encodeURIComponent(entry.key)}/${encodeURIComponent(locale)}/reset`,
      ),
    onSuccess: done,
  });

  const error = save.error ?? reset.error;
  const busy = save.isPending || reset.isPending;

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label={`${t("translations.target")} ${entry.key}`}
          data-testid={`translation-input-${testId}`}
          value={draft}
          disabled={!canManage || busy}
          onChange={(event) => setDraft(event.target.value)}
          className="min-w-40 flex-1"
        />
        <select
          aria-label={t("translations.status")}
          data-testid={`translation-status-select-${testId}`}
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          value={status}
          disabled={!canManage || busy}
          onChange={(event) => setStatus(event.target.value as "approved" | "needs_review")}
        >
          <option value="approved">{t("translations.approved")}</option>
          <option value="needs_review">{t("translations.needs_review")}</option>
        </select>
        <Button
          type="button"
          variant="secondary"
          data-testid={`translation-suggest-${testId}`}
          disabled={!canManage || busy || suggest.isPending}
          onClick={() => {
            setAiNotice(null);
            suggest.mutate();
          }}
        >
          {suggest.isPending ? t("translations.suggesting") : t("translations.suggest")}
        </Button>
        <Button
          type="button"
          data-testid={`translation-save-${testId}`}
          disabled={!canManage || busy || draft.trim() === ""}
          onClick={() => save.mutate()}
        >
          {t("translations.save")}
        </Button>
        {entry.layer === "school" ? (
          <Button
            type="button"
            variant="outline"
            data-testid={`translation-reset-${testId}`}
            disabled={!canManage || busy}
            onClick={() => reset.mutate()}
          >
            {t("translations.reset")}
          </Button>
        ) : null}
      </div>
      {save.isSuccess || reset.isSuccess ? (
        <p className="text-xs text-muted-foreground">{t("translations.saved")}</p>
      ) : null}
      {aiNotice ? (
        <p className="text-xs text-muted-foreground" data-testid={`translation-ai-notice-${testId}`}>
          {t(aiNotice)}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-xs text-destructive">
          {t(errorKey(error))}
        </p>
      ) : null}
    </div>
  );
}

export function TranslationsPage() {
  const { t, reload } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const canView = hasPermission(user?.permissions, "i18n.view");
  const canManage = hasPermission(user?.permissions, "i18n.manage");
  const [draft, setDraft] = useState<Filters>(DEFAULT_FILTERS);
  const [filters, setFilters] = useState<Filters>(draft);
  const [preview, setPreview] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [importNamespace, setImportNamespace] = useState("core");
  const [importFormat, setImportFormat] = useState<"json" | "csv">("json");
  const [importStatus, setImportStatus] = useState("approved");
  const [importContent, setImportContent] = useState("");
  const [importSummary, setImportSummary] = useState<{ imported: number; unchanged: number } | null>(
    null,
  );

  const namespaces = useQuery({
    queryKey: ["translation-namespaces"],
    queryFn: () => api.get<{ items: string[] }>("/api/v1/i18n/editor/namespaces"),
    enabled: canView,
    retry: false,
  });

  const entries = useQuery({
    queryKey: ["translations", filters],
    queryFn: () => {
      const params = new URLSearchParams({
        locale: filters.locale,
        limit: "500",
      });
      if (filters.namespace) params.set("namespace", filters.namespace);
      if (filters.q.trim()) params.set("q", filters.q.trim());
      if (filters.status) params.set("status", filters.status);
      if (filters.layer) params.set("layer", filters.layer);
      return api.get<EntryList>(`/api/v1/i18n/editor/entries?${params.toString()}`);
    },
    enabled: canView,
    retry: false,
  });

  const stats = useQuery({
    queryKey: ["translation-stats", filters.locale, filters.namespace],
    queryFn: () => {
      const params = new URLSearchParams({ locale: filters.locale });
      if (filters.namespace) params.set("namespace", filters.namespace);
      return api.get<TranslationStats>(`/api/v1/i18n/editor/stats?${params.toString()}`);
    },
    enabled: canView,
    retry: false,
  });

  const items = useMemo(() => entries.data?.items ?? [], [entries.data]);
  const selectedEntry = useMemo(
    () => items.find((entry) => entryId(entry) === selected) ?? null,
    [items, selected],
  );

  const apply = (event: FormEvent) => {
    event.preventDefault();
    setFilters({ ...draft });
    setSelected(null);
  };

  const clear = () => {
    const next = { ...DEFAULT_FILTERS, locale: draft.locale };
    setDraft(next);
    setFilters(next);
    setSelected(null);
  };

  const importEntries = useMutation({
    mutationFn: () =>
      api.post<{ imported: number; unchanged: number }>("/api/v1/i18n/editor/import", {
        namespace: importNamespace,
        locale: filters.locale,
        format: importFormat,
        content: importContent,
        status: importStatus,
      }),
    onSuccess: async (result) => {
      setImportSummary(result);
      setImportContent("");
      await queryClient.invalidateQueries({ queryKey: ["translations"] });
      await queryClient.invalidateQueries({ queryKey: ["translation-stats"] });
      reload();
    },
  });

  async function download(format: "json" | "csv") {
    const params = new URLSearchParams({ locale: filters.locale, format });
    if (filters.namespace) params.set("namespace", filters.namespace);
    const token = getAccessToken();
    const response = await fetch(`${API_URL}/api/v1/i18n/editor/export?${params.toString()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error("export failed");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `translations-${filters.locale}-${filters.namespace || "all"}.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (!canView) {
    return (
      <div className="space-y-3" data-testid="translations-page">
        <h1 className="text-2xl font-semibold">{t("translations.title")}</h1>
        <p role="alert" className="text-sm text-destructive">
          {t("translations.permission_denied")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="translations-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("translations.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("translations.description")}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          data-testid="translations-toggle-preview"
          onClick={() => setPreview((value) => !value)}
        >
          {preview ? t("translations.table_mode") : t("translations.in_context")}
        </Button>
      </div>

      <form
        className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-2 lg:grid-cols-5"
        onSubmit={apply}
      >
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">{t("common.language")}</span>
          <select
            aria-label={t("common.language")}
            className="h-9 w-full rounded-md border border-input bg-background px-2"
            value={draft.locale}
            onChange={(event) => setDraft({ ...draft, locale: event.target.value })}
          >
            <option value="am">{t("settings.enum.am")}</option>
            <option value="en">{t("settings.enum.en")}</option>
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">{t("translations.module")}</span>
          <select
            aria-label={t("translations.module")}
            className="h-9 w-full rounded-md border border-input bg-background px-2"
            value={draft.namespace}
            onChange={(event) => setDraft({ ...draft, namespace: event.target.value })}
          >
            <option value="">{t("translations.all_modules")}</option>
            {(namespaces.data?.items ?? []).map((namespace) => (
              <option key={namespace} value={namespace}>
                {namespace}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">{t("translations.search")}</span>
          <Input
            aria-label={t("translations.search")}
            value={draft.q}
            onChange={(event) => setDraft({ ...draft, q: event.target.value })}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">{t("translations.status")}</span>
          <select
            aria-label={t("translations.status")}
            className="h-9 w-full rounded-md border border-input bg-background px-2"
            value={draft.status}
            onChange={(event) => setDraft({ ...draft, status: event.target.value })}
          >
            <option value="">{t("translations.all_statuses")}</option>
            <option value="missing">{t("translations.missing")}</option>
            <option value="needs_review">{t("translations.needs_review")}</option>
            <option value="approved">{t("translations.approved")}</option>
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">{t("translations.layer")}</span>
          <select
            aria-label={t("translations.layer")}
            className="h-9 w-full rounded-md border border-input bg-background px-2"
            value={draft.layer}
            onChange={(event) => setDraft({ ...draft, layer: event.target.value })}
          >
            <option value="">{t("translations.all_layers")}</option>
            <option value="school">{t("translations.layer.school")}</option>
            <option value="central">{t("translations.layer.central")}</option>
            <option value="default">{t("translations.layer.default")}</option>
          </select>
        </label>
        <div className="flex items-end gap-2 md:col-span-2 lg:col-span-5">
          <Button type="submit" data-testid="translations-apply">
            {t("translations.apply")}
          </Button>
          <Button type="button" variant="outline" onClick={clear}>
            {t("translations.clear")}
          </Button>
          <Button
            type="button"
            variant="outline"
            data-testid="translations-export-json"
            onClick={() => void download("json")}
          >
            {t("translations.export_json")}
          </Button>
          <Button
            type="button"
            variant="outline"
            data-testid="translations-export-csv"
            onClick={() => void download("csv")}
          >
            {t("translations.export_csv")}
          </Button>
        </div>
      </form>

      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
        <span>{t("translations.total", { count: stats.data?.total ?? 0 })}</span>
        <span>{t("translations.missing_count", { count: stats.data?.missing ?? 0 })}</span>
        <span>{t("translations.review_count", { count: stats.data?.needs_review ?? 0 })}</span>
        <span>{t("translations.overrides_count", { count: stats.data?.overrides ?? 0 })}</span>
      </div>

      {!canManage ? (
        <p className="text-sm text-muted-foreground">{t("translations.permission_denied")}</p>
      ) : null}

      {entries.isLoading ? (
        <LoadingState label={t("translations.loading")} />
      ) : entries.isError ? (
        <ErrorState
          title={t("common.error")}
          requestId={requestIdOf(entries.error)}
          requestIdLabel={t("common.request_id")}
          retry={
            <Button size="sm" variant="outline" onClick={() => void entries.refetch()}>
              {t("common.retry")}
            </Button>
          }
        />
      ) : null}

      {preview ? (
        <Card data-testid="in-context-preview">
          <CardHeader>
            <CardTitle>{t("translations.in_context")}</CardTitle>
            <CardDescription>{t("translations.in_context_hint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {items.slice(0, 12).map((entry) => (
                <button
                  key={entryId(entry)}
                  type="button"
                  data-testid={`translation-preview-${entry.namespace}-${entry.key}`}
                  className={`rounded-md border px-2 py-1 text-sm ${
                    selected === entryId(entry)
                      ? "border-primary bg-primary/10"
                      : "border-border bg-background hover:bg-muted"
                  }`}
                  onClick={() => setSelected(entryId(entry))}
                >
                  {entry.value || entry.source}
                </button>
              ))}
            </div>
            {selectedEntry ? (
              <div className="space-y-2 rounded-md border border-border p-3">
                <p className="font-mono text-xs text-muted-foreground">
                  {selectedEntry.namespace}:{selectedEntry.key}
                </p>
                <p className="text-sm">{selectedEntry.source}</p>
                <EntryEditor
                  entry={selectedEntry}
                  locale={filters.locale}
                  canManage={canManage}
                  testId={`preview-${selectedEntry.key}`}
                />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{t("translations.choose_key")}</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent
            className="overflow-x-auto p-0"
            tabIndex={0}
            role="region"
            aria-label={t("translations.title")}
          >
            <table className="ui-min-w-40 w-full text-left text-sm">
              <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("translations.key")}</th>
                  <th className="px-4 py-3">{t("translations.source")}</th>
                  <th className="px-4 py-3">{t("translations.target")}</th>
                  <th className="px-4 py-3">{t("translations.status")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((entry) => (
                  <tr
                    key={entryId(entry)}
                    data-testid={`translation-row-${entry.namespace}-${entry.key}`}
                    className="border-b border-border align-top last:border-0"
                  >
                    <td className="px-4 py-3">
                      <p className="font-mono text-xs">{entry.key}</p>
                      <p className="text-xs text-muted-foreground">{entry.namespace}</p>
                    </td>
                    <td className="px-4 py-3">{entry.source}</td>
                    <td className="px-4 py-3">
                      <EntryEditor
                        entry={entry}
                        locale={filters.locale}
                        canManage={canManage}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <EntryState entry={entry} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!entries.isLoading && !entries.isError && items.length === 0 ? (
              <EmptyState className="m-4" title={t("translations.empty")} />
            ) : null}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{t("translations.import")}</CardTitle>
          <CardDescription>{t("translations.import_hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-3">
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("translations.module")}</span>
              <select
                aria-label={`${t("translations.import")} ${t("translations.module")}`}
                className="h-9 w-full rounded-md border border-input bg-background px-2"
                value={importNamespace}
                onChange={(event) => setImportNamespace(event.target.value)}
              >
                {(namespaces.data?.items ?? ["core"]).map((namespace) => (
                  <option key={namespace} value={namespace}>
                    {namespace}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("translations.status")}</span>
              <select
                aria-label={`${t("translations.import")} ${t("translations.status")}`}
                className="h-9 w-full rounded-md border border-input bg-background px-2"
                value={importStatus}
                onChange={(event) => setImportStatus(event.target.value)}
              >
                <option value="approved">{t("translations.approved")}</option>
                <option value="needs_review">{t("translations.needs_review")}</option>
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("translations.import")}</span>
              <select
                aria-label={`${t("translations.import")} format`}
                className="h-9 w-full rounded-md border border-input bg-background px-2"
                value={importFormat}
                onChange={(event) => setImportFormat(event.target.value as "json" | "csv")}
              >
                <option value="json">{t("common.format.json")}</option>
                <option value="csv">{t("common.format.csv")}</option>
              </select>
            </label>
          </div>
          <textarea
            aria-label={t("translations.import")}
            data-testid="translation-import-content"
            className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
            value={importContent}
            onChange={(event) => setImportContent(event.target.value)}
          />
          <div className="flex items-center gap-3">
            <Button
              type="button"
              data-testid="translation-import-button"
              disabled={!canManage || importEntries.isPending || importContent.trim() === ""}
              onClick={() => {
                setImportSummary(null);
                importEntries.mutate();
              }}
            >
              {t("translations.import_button")}
            </Button>
            {importSummary ? (
              <p className="text-sm text-muted-foreground" data-testid="translation-import-summary">
                {t("translations.import_summary", {
                  imported: importSummary.imported,
                  unchanged: importSummary.unchanged,
                })}
              </p>
            ) : null}
            {importEntries.error ? (
              <p role="alert" className="text-sm text-destructive">
                {t(errorKey(importEntries.error))}
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
