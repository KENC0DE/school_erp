import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { api } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

type FieldType = "string" | "number" | "boolean" | "enum" | "list" | "secret";
type Source = "code" | "central" | "instance";

export interface SettingFieldSpec {
  module: string;
  key: string;
  type: FieldType;
  default: unknown;
  label_key: string;
  enum: string[] | null;
  minimum: number | null;
  maximum: number | null;
  max_length: number | null;
  secret: boolean;
  value: unknown;
  source: Source;
}

export interface SettingModule {
  module: string;
  label_key: string;
  fields: SettingFieldSpec[];
}

interface SettingsResponse {
  items: SettingModule[];
  next_cursor: string | null;
}

const SOURCE_KEYS: Record<Source, string> = {
  code: "settings.source.code",
  central: "settings.source.central",
  instance: "settings.source.instance",
};

/** Turn an API value into the string an input control edits. */
function toDraft(field: SettingFieldSpec): string {
  const value = field.value;
  if (field.type === "list" || Array.isArray(value)) {
    return Array.isArray(value) ? value.map(String).join(", ") : "";
  }
  if (field.type === "boolean") return value === true ? "true" : "false";
  return value === null || value === undefined ? "" : String(value);
}

/** Turn the edited string back into the JSON value the API validates. */
function fromDraft(field: SettingFieldSpec, draft: string): unknown {
  if (field.type === "boolean") return draft === "true";
  if (field.type === "number") return draft.trim() === "" ? null : Number(draft);
  if (field.type === "list") {
    return draft
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return draft;
}

function SourceBadge({ source }: { source: Source }) {
  const { t } = useI18n();
  return <Badge>{t(SOURCE_KEYS[source] ?? "settings.source.code")}</Badge>;
}

function FieldControl({
  field,
  draft,
  onChange,
  disabled,
}: {
  field: SettingFieldSpec;
  draft: string;
  onChange: (next: string) => void;
  disabled: boolean;
}) {
  const { t } = useI18n();
  const label = t(field.label_key);

  if (field.type === "boolean") {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          aria-label={label}
          checked={draft === "true"}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked ? "true" : "false")}
        />
        <span>{t("common.enabled")}</span>
      </label>
    );
  }

  if (field.type === "enum" && field.enum) {
    return (
      <select
        aria-label={label}
        value={draft}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
      >
        {field.enum.map((option) => (
          <option key={option} value={option}>
            {t(`settings.enum.${option}`)}
          </option>
        ))}
      </select>
    );
  }

  return (
    <Input
      aria-label={label}
      type={field.secret ? "password" : field.type === "number" ? "number" : "text"}
      value={draft}
      disabled={disabled}
      min={field.minimum ?? undefined}
      max={field.maximum ?? undefined}
      maxLength={field.max_length ?? undefined}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

function FieldRow({
  field,
  canManage,
}: {
  field: SettingFieldSpec;
  canManage: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(() => toDraft(field));

  useEffect(() => {
    setDraft(toDraft(field));
  }, [field]);

  const path = `/api/v1/settings/${encodeURIComponent(field.module)}/${encodeURIComponent(field.key)}`;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["settings"] });

  const save = useMutation({
    mutationFn: (value: unknown) => api.put<SettingFieldSpec>(path, { value }),
    onSuccess: () => void refresh(),
  });

  const reset = useMutation({
    mutationFn: () => api.del<SettingFieldSpec>(path),
    onSuccess: () => void refresh(),
  });

  const error = save.error ?? reset.error;
  const denied = error instanceof ApiRequestError && error.code === "PERMISSION_DENIED";
  const busy = save.isPending || reset.isPending;

  return (
    <div className="grid gap-2 border-b border-border py-4 last:border-0 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_auto] md:items-center md:gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{t(field.label_key)}</span>
        <SourceBadge source={field.source} />
      </div>
      <div>
        <FieldControl
          field={field}
          draft={draft}
          onChange={setDraft}
          disabled={!canManage || busy}
        />
        {error ? (
          <p className="pt-1 text-xs text-destructive">
            {denied ? t("error.permission_denied") : t("common.error")}
          </p>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          disabled={!canManage || busy}
          onClick={() => save.mutate(fromDraft(field, draft))}
        >
          {t("settings.save")}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!canManage || busy || field.source === "code"}
          onClick={() => reset.mutate()}
        >
          {t("settings.reset")}
        </Button>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];
  const canManage = permissions.includes("*") || permissions.includes("settings.manage");
  const canViewModules =
    permissions.includes("*") ||
    permissions.includes("modules.view") ||
    permissions.includes("modules.manage");
  const canViewLanguages =
    permissions.includes("*") ||
    permissions.includes("i18n.view") ||
    permissions.includes("i18n.manage");

  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<SettingsResponse>("/api/v1/settings"),
    retry: false,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">{t("settings.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("settings.intro")}</p>
      </div>

      {settings.isLoading ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : null}
      {settings.isError ? (
        <p className="text-sm text-destructive">{t("common.error")}</p>
      ) : null}

      {canViewModules ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settings.modules.title")}</CardTitle>
            <CardDescription>{t("settings.modules.hint")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              to="/settings/modules"
              className="text-sm font-medium text-primary hover:underline"
            >
              {t("settings.modules.link")}
            </Link>
          </CardContent>
        </Card>
      ) : null}

      {canViewLanguages ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settings.languages.title")}</CardTitle>
            <CardDescription>{t("settings.languages.hint")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              to="/settings/languages"
              className="text-sm font-medium text-primary hover:underline"
            >
              {t("settings.languages.link")}
            </Link>
          </CardContent>
        </Card>
      ) : null}

      {(settings.data?.items ?? []).map((module) => (
        <Card key={module.module}>
          <CardHeader>
            <CardTitle>{t(module.label_key)}</CardTitle>
          </CardHeader>
          <CardContent>
            {module.fields.map((field) => (
              <FieldRow key={`${field.module}.${field.key}`} field={field} canManage={canManage} />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
