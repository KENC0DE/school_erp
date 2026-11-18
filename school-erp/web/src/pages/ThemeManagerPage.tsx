import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ChangeEvent, type FormEvent } from "react";
import { EmptyState, ErrorState, LoadingState } from "@erp/ui-web";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { api } from "../lib/api";
import { requestIdOf } from "../lib/errors";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";
import { useTheme } from "../providers/ThemeProvider";

type Format = "css" | "json" | "registry";

interface ThemeSummary {
  key: string;
  name: string;
  description: string | null;
  is_default: boolean;
  is_active: boolean;
  is_builtin: boolean;
  source: string;
  source_url: string | null;
  row_version: number | null;
  valid: boolean;
}

interface ContrastRow {
  mode: "light" | "dark";
  foreground_token: string;
  background_token: string;
  foreground: string;
  background: string;
  ratio: number;
  minimum: number;
  passes: boolean;
  message: string;
}

interface ThemeIssue {
  code: string;
  mode: string | null;
  message: string;
  token?: string;
  ratio?: number;
  minimum?: number;
}

interface ThemeDetail extends ThemeSummary {
  tokens: Record<string, Record<string, string>>;
  issues: ThemeIssue[];
  contrast: ContrastRow[];
  css: Record<string, string>;
  mobile: Record<string, unknown>;
}

interface PreviewResult {
  valid: boolean;
  key: string;
  name: string;
  source: string;
  issues: ThemeIssue[];
  contrast: ContrastRow[];
  tokens: Record<string, Record<string, string>>;
  css: Record<string, string>;
  mobile: Record<string, unknown>;
  warnings: string[];
  fallback: { key: string; name: string } | null;
}

function hasPermission(permissions: string[] | undefined, permission: string): boolean {
  return Boolean(permissions?.includes("*") || permissions?.includes(permission));
}

function errorMessage(error: unknown): ThemeIssue[] {
  if (error instanceof ApiRequestError) {
    const details = error.details as { issues?: ThemeIssue[] } | undefined;
    if (details?.issues) return details.issues;
    return [{ code: error.code, mode: null, message: error.message }];
  }
  return [];
}

function Palette({ tokens }: { tokens: Record<string, string> }) {
  const keys = ["background", "foreground", "primary", "primary-foreground", "muted", "accent", "sidebar"];
  return (
    <div className="flex flex-wrap gap-2" data-testid="theme-palette">
      {keys.map((key) => (
        <div key={key} className="w-24">
          <div
            className="h-10 rounded border border-border"
            style={{ backgroundColor: tokens[key] }}
            aria-hidden="true"
          />
          <p className="truncate text-xs text-muted-foreground">{key}</p>
        </div>
      ))}
    </div>
  );
}

function ContrastTable({ rows }: { rows: ContrastRow[] }) {
  const { t } = useI18n();
  return (
    <div className="overflow-x-auto">
      <table className="ui-min-w-34 w-full text-left text-sm" data-testid="theme-contrast-table">
        <thead className="border-b border-border text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-2 py-2">{t("themes.mode")}</th>
            <th className="px-2 py-2">{t("themes.pair")}</th>
            <th className="px-2 py-2">{t("themes.ratio")}</th>
            <th className="px-2 py-2">{t("themes.result")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.mode}-${row.foreground_token}-${row.background_token}`} className="border-b border-border last:border-0">
              <td className="px-2 py-2">{t(`themes.mode.${row.mode}`)}</td>
              <td className="px-2 py-2 font-mono text-xs">
                {row.foreground_token} / {row.background_token}
              </td>
              <td className="px-2 py-2">{row.ratio.toFixed(2)}:1</td>
              <td className="px-2 py-2">
                <Badge>{t(row.passes ? "themes.pass" : "themes.fail")}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IssueList({ issues }: { issues: ThemeIssue[] }) {
  const { t } = useI18n();
  if (issues.length === 0) return null;
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3" data-testid="theme-issues">
      <p className="text-sm font-medium text-destructive">{t("themes.issues")}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-destructive">
        {issues.map((issue, index) => (
          <li key={`${issue.code}-${index}`}>{issue.message}</li>
        ))}
      </ul>
    </div>
  );
}

function ThemePreview({ result }: { result: PreviewResult | ThemeDetail }) {
  const { t } = useI18n();
  return (
    <div className="space-y-4" data-testid="theme-preview">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{result.valid ? t("themes.valid") : t("themes.invalid")}</Badge>
        <span className="text-sm font-medium">{result.name}</span>
        <span className="font-mono text-xs text-muted-foreground">{result.key}</span>
      </div>
      <IssueList issues={result.issues} />
      {!result.valid && "fallback" in result && result.fallback ? (
        <p className="text-sm text-muted-foreground">
          {t("themes.fallback", { name: result.fallback.name })}
        </p>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        {(["light", "dark"] as const).map((mode) => (
          <div key={mode} className="space-y-2 rounded-md border border-border p-3">
            <p className="text-sm font-medium">{t(`themes.mode.${mode}`)}</p>
            <Palette tokens={result.tokens[mode] ?? {}} />
            <div
              className="rounded-md p-3"
              style={{
                backgroundColor: result.tokens[mode]?.background,
                color: result.tokens[mode]?.foreground,
              }}
            >
              <p className="text-sm font-semibold">{t("themes.sample_heading")}</p>
              <p className="text-xs">{t("themes.sample_body")}</p>
              <span
                className="mt-2 inline-block rounded px-2 py-1 text-xs"
                style={{
                  backgroundColor: result.tokens[mode]?.primary,
                  color: result.tokens[mode]?.["primary-foreground"],
                }}
              >
                {t("themes.sample_button")}
              </span>
            </div>
          </div>
        ))}
      </div>
      <div>
        <p className="mb-1 text-sm font-medium">{t("themes.contrast")}</p>
        <ContrastTable rows={result.contrast} />
      </div>
    </div>
  );
}

function ImportForm({ onImported }: { onImported: (key: string) => void }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [format, setFormat] = useState<Format>("css");
  const [content, setContent] = useState("");
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [description, setDescription] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);

  const payload = () => ({
    format,
    content,
    name: name.trim() || null,
    key: key.trim() || null,
  });

  const previewMutation = useMutation({
    mutationFn: () => api.post<PreviewResult>("/api/v1/themes/preview", payload()),
    onSuccess: setPreview,
  });

  const save = useMutation({
    mutationFn: () =>
      api.post<ThemeDetail>("/api/v1/themes/import", {
        ...payload(),
        description: description.trim() || null,
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["themes"] });
      onImported(result.key);
      setContent("");
      setPreview(null);
    },
  });

  const readFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setContent(await file.text());
    if (file.name.endsWith(".json")) setFormat("json");
    if (file.name.endsWith(".css")) setFormat("css");
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (content.trim() === "") return;
    previewMutation.mutate();
  };

  const errors = errorMessage(save.error ?? previewMutation.error);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("themes.import")}</CardTitle>
        <CardDescription>{t("themes.import_hint")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form className="space-y-3" onSubmit={submit}>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("themes.format")}</span>
              <select
                aria-label={t("themes.format")}
                data-testid="theme-format"
                className="h-9 w-full rounded-md border border-input bg-background px-2"
                value={format}
                onChange={(event) => setFormat(event.target.value as Format)}
              >
                <option value="css">{t("themes.format.css")}</option>
                <option value="json">{t("themes.format.json")}</option>
                <option value="registry">{t("themes.format.registry")}</option>
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("themes.name")}</span>
              <Input
                aria-label={t("themes.name")}
                data-testid="theme-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("themes.key")}</span>
              <Input
                aria-label={t("themes.key")}
                data-testid="theme-key"
                value={key}
                onChange={(event) => setKey(event.target.value)}
              />
            </label>
          </div>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">{t("themes.description_field")}</span>
            <Input
              aria-label={t("themes.description_field")}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">
              {format === "registry" ? t("themes.registry_url") : t("themes.content")}
            </span>
            <textarea
              aria-label={format === "registry" ? t("themes.registry_url") : t("themes.content")}
              data-testid="theme-content"
              className="min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
              value={content}
              placeholder={t("themes.content_placeholder")}
              onChange={(event) => setContent(event.target.value)}
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="file"
              accept=".json,.css,application/json,text/css"
              aria-label={t("themes.choose_file")}
              className="text-sm"
              onChange={(event) => void readFile(event)}
            />
            <Button
              type="submit"
              variant="outline"
              data-testid="theme-preview-button"
              disabled={content.trim() === "" || previewMutation.isPending}
            >
              {t("themes.preview")}
            </Button>
            <Button
              type="button"
              data-testid="theme-save-button"
              disabled={!preview?.valid || save.isPending}
              onClick={() => save.mutate()}
            >
              {t("themes.save")}
            </Button>
            {save.isSuccess ? (
              <p className="text-sm text-muted-foreground">{t("themes.saved")}</p>
            ) : null}
          </div>
        </form>
        {errors.length > 0 ? <IssueList issues={errors} /> : null}
        {preview ? <ThemePreview result={preview} /> : null}
      </CardContent>
    </Card>
  );
}

export function ThemeManagerPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { reload: reloadActive } = useTheme();
  const queryClient = useQueryClient();
  const canView = hasPermission(user?.permissions, "themes.view");
  const canManage = hasPermission(user?.permissions, "themes.manage");
  const [selected, setSelected] = useState<string | null>(null);

  const themes = useQuery({
    queryKey: ["themes"],
    queryFn: () => api.get<{ items: ThemeSummary[] }>("/api/v1/themes"),
    enabled: canView,
    retry: false,
  });

  const detail = useQuery({
    queryKey: ["theme", selected],
    queryFn: () => api.get<ThemeDetail>(`/api/v1/themes/${encodeURIComponent(selected!)}`),
    enabled: canView && selected !== null,
    retry: false,
  });

  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: ["themes"] });
    await queryClient.invalidateQueries({ queryKey: ["theme"] });
    await reloadActive();
  };

  const makeDefault = useMutation({
    mutationFn: (key: string) => api.post(`/api/v1/themes/${encodeURIComponent(key)}/default`),
    onSuccess: done,
  });
  const setAvailability = useMutation({
    mutationFn: ({ key, active, version }: { key: string; active: boolean; version: number }) =>
      api.patch(`/api/v1/themes/${encodeURIComponent(key)}`, {
        row_version: version,
        is_active: active,
      }),
    onSuccess: done,
  });
  const remove = useMutation({
    mutationFn: (key: string) => api.del(`/api/v1/themes/${encodeURIComponent(key)}`),
    onSuccess: async (_, key) => {
      if (selected === key) setSelected(null);
      await done();
    },
  });

  const actionError =
    errorMessage(makeDefault.error ?? setAvailability.error ?? remove.error)[0] ?? null;

  if (!canView) {
    return (
      <div className="space-y-3" data-testid="theme-manager-page">
        <h1 className="text-2xl font-semibold">{t("themes.title")}</h1>
        <p role="alert" className="text-sm text-destructive">
          {t("error.permission_denied")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="theme-manager-page">
      <div>
        <h1 className="text-2xl font-semibold">{t("themes.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("themes.description")}</p>
      </div>

      {canManage ? (
        <ImportForm
          onImported={(key) => {
            setSelected(key);
            void reloadActive();
          }}
        />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("themes.list")}</CardTitle>
          <CardDescription>{t("themes.list_hint")}</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {themes.isLoading ? (
            <LoadingState label={t("themes.loading")} />
          ) : themes.isError ? (
            <ErrorState
              title={t("common.error")}
              requestId={requestIdOf(themes.error)}
              requestIdLabel={t("common.request_id")}
              retry={
                <Button size="sm" variant="outline" onClick={() => void themes.refetch()}>
                  {t("common.retry")}
                </Button>
              }
            />
          ) : null}
          {actionError ? (
            <p role="alert" className="pb-2 text-sm text-destructive">
              {actionError.message}
            </p>
          ) : null}
          <table className="ui-min-w-45 w-full text-left text-sm">
            <thead className="border-b border-border text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">{t("themes.name")}</th>
                <th className="px-3 py-2">{t("themes.status")}</th>
                <th className="px-3 py-2">{t("themes.source")}</th>
                <th className="px-3 py-2">{t("themes.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {(themes.data?.items ?? []).map((theme) => (
                <tr
                  key={theme.key}
                  data-testid={`theme-row-${theme.key}`}
                  className="border-b border-border align-top last:border-0"
                >
                  <td className="px-3 py-3">
                    <p className="font-medium">{theme.name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{theme.key}</p>
                    {theme.description ? (
                      <p className="text-xs text-muted-foreground">{theme.description}</p>
                    ) : null}
                  </td>
                  <td className="space-y-1 px-3 py-3">
                    {theme.is_default ? <Badge>{t("themes.default")}</Badge> : null}
                    <Badge>
                      {t(theme.is_active ? "themes.available" : "themes.hidden")}
                    </Badge>
                    {theme.valid ? null : <Badge>{t("themes.broken")}</Badge>}
                  </td>
                  <td className="px-3 py-3 text-xs text-muted-foreground">{theme.source}</td>
                  <td className="space-y-1 px-3 py-3">
                    <div className="flex flex-wrap gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        data-testid={`theme-preview-row-${theme.key}`}
                        onClick={() => setSelected(theme.key)}
                      >
                        {t("themes.preview")}
                      </Button>
                      {canManage && !theme.is_default ? (
                        <Button
                          type="button"
                          variant="ghost"
                          data-testid={`theme-default-${theme.key}`}
                          disabled={makeDefault.isPending || !theme.valid}
                          onClick={() => makeDefault.mutate(theme.key)}
                        >
                          {t("themes.set_default")}
                        </Button>
                      ) : null}
                      {canManage && theme.row_version !== null ? (
                        <Button
                          type="button"
                          variant="ghost"
                          data-testid={`theme-toggle-${theme.key}`}
                          disabled={setAvailability.isPending}
                          onClick={() =>
                            setAvailability.mutate({
                              key: theme.key,
                              active: !theme.is_active,
                              version: theme.row_version!,
                            })
                          }
                        >
                          {t(theme.is_active ? "themes.deactivate" : "themes.activate")}
                        </Button>
                      ) : null}
                      {canManage && !theme.is_builtin ? (
                        <Button
                          type="button"
                          variant="ghost"
                          data-testid={`theme-delete-${theme.key}`}
                          disabled={remove.isPending}
                          onClick={() => {
                            if (window.confirm(t("themes.delete_confirm", { name: theme.name }))) {
                              remove.mutate(theme.key);
                            }
                          }}
                        >
                          {t("themes.delete")}
                        </Button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!themes.isLoading && !themes.isError && (themes.data?.items ?? []).length === 0 ? (
            <EmptyState className="my-2" title={t("themes.no_items")} />
          ) : null}
        </CardContent>
      </Card>

      {selected ? (
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>{t("themes.detail")}</CardTitle>
                <CardDescription>{t("themes.detail_hint")}</CardDescription>
              </div>
              <Button type="button" variant="outline" onClick={() => setSelected(null)}>
                {t("themes.close")}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail.isLoading ? (
              <LoadingState label={t("themes.loading")} rows={2} columns={3} />
            ) : detail.isError ? (
              <ErrorState
                title={t("common.error")}
                requestId={requestIdOf(detail.error)}
                requestIdLabel={t("common.request_id")}
                retry={
                  <Button size="sm" variant="outline" onClick={() => void detail.refetch()}>
                    {t("common.retry")}
                  </Button>
                }
              />
            ) : null}
            {detail.data ? <ThemePreview result={detail.data} /> : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
