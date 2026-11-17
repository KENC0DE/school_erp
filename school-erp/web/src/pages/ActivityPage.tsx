import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { api } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

interface ActivityEntry {
  seq: number;
  ts: string | null;
  actor_type: string;
  actor_id: string | null;
  actor_name: string | null;
  on_behalf_of: string | null;
  on_behalf_of_name: string | null;
  via: string;
  module: string | null;
  entity_type: string | null;
  entity_id: string | null;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string | null;
  reverts_id: number | null;
  revertible?: boolean;
}

interface ActivityList {
  items: ActivityEntry[];
  next_cursor: string | null;
}

interface ActivityOptions {
  modules: string[];
  actions: string[];
  actors: { id: string; actor_type: string; name: string | null }[];
}

interface Filters {
  actor: string;
  module: string;
  action: string;
  entityType: string;
  entityId: string;
  from: string;
  to: string;
}

const EMPTY_FILTERS: Filters = {
  actor: "",
  module: "",
  action: "",
  entityType: "",
  entityId: "",
  from: "",
  to: "",
};

const WILDCARD = "*";

function hasPermission(permissions: string[] | undefined, permission: string): boolean {
  return Boolean(permissions?.includes(WILDCARD) || permissions?.includes(permission));
}

function buildQuery(filters: Filters): string {
  const params = new URLSearchParams();
  if (filters.actor) params.set("actor_id", filters.actor);
  if (filters.module) params.set("module", filters.module);
  if (filters.action) params.set("action", filters.action);
  if (filters.entityType) params.set("entity_type", filters.entityType);
  if (filters.entityId) params.set("entity_id", filters.entityId);
  if (filters.from) params.set("date_from", `${filters.from}T00:00:00.000Z`);
  if (filters.to) params.set("date_to", `${filters.to}T23:59:59.999Z`);
  const query = params.toString();
  return query ? `?${query}` : "";
}

function moduleLabel(translate: (key: string) => string, module: string | null): string {
  if (!module) return "";
  const key = `settings.module.${module}`;
  const label = translate(key);
  return label === key
    ? module.charAt(0).toUpperCase() + module.slice(1)
    : label;
}

function actorLabel(
  translate: (key: string) => string,
  entry: ActivityEntry,
): string | null {
  if (entry.actor_name) return entry.actor_name;
  if (entry.actor_type === "controller") return translate("activity.controller");
  if (entry.actor_type === "system") return translate("activity.system");
  return entry.actor_id;
}

function diffFields(entry: ActivityEntry): string[] {
  const keys = new Set<string>([
    ...Object.keys(entry.before ?? {}),
    ...Object.keys(entry.after ?? {}),
  ]);
  return [...keys].sort();
}

function displayValue(value: unknown): string {
  if (value === undefined || value === null) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ChangesTable({ entry }: { entry: ActivityEntry }) {
  const { t } = useI18n();
  const fields = diffFields(entry);
  return (
    <div className="mt-3 overflow-x-auto" data-testid={`activity-changes-${entry.seq}`}>
      {fields.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("activity.no_changes")}</p>
      ) : (
        <table className="w-full min-w-[28rem] text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="py-2 pr-4 font-medium">{t("activity.field")}</th>
              <th className="py-2 pr-4 font-medium">{t("activity.before")}</th>
              <th className="py-2 font-medium">{t("activity.after")}</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => (
              <tr key={field} className="border-t border-border align-top">
                <td className="py-2 pr-4 font-medium">{field}</td>
                <td className="py-2 pr-4 text-muted-foreground break-all">
                  {displayValue(entry.before?.[field])}
                </td>
                <td className="py-2 break-all">{displayValue(entry.after?.[field])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function EntryCard({ entry }: { entry: ActivityEntry }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [showChanges, setShowChanges] = useState(false);
  const [reverting, setReverting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isRestore = entry.action.endsWith(".delete");

  const submitRevert = async () => {
    setBusy(true);
    setError(null);
    try {
      const action = isRestore ? "restore" : "revert";
      await api.post<Record<string, unknown>>(
        `/api/v1/audit/activity/${entry.seq}/${action}`,
        { reason },
      );
      setReverting(false);
      setReason("");
      await queryClient.invalidateQueries({ queryKey: ["activity"] });
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  };
  const actor = actorLabel(t, entry);
  const module = moduleLabel(t, entry.module);
  const hasValues = diffFields(entry).length > 0;

  return (
    <div className="border-b border-border py-4 last:border-0" data-testid={`activity-entry-${entry.seq}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <p className="font-medium">{entry.action}</p>
          <p className="text-sm text-muted-foreground">
            {module ? <span className="font-medium text-foreground">{module} · </span> : null}
            {entry.entity_type ?? "—"}
            {entry.entity_id ? ` · ${entry.entity_id}` : ""}
          </p>
          <p className="text-sm text-muted-foreground" data-testid={`activity-actor-${entry.seq}`}>
            {actor}
            {entry.via && entry.via !== "web" ? (
              <Badge className="ml-2">{t(`activity.via.${entry.via}`)}</Badge>
            ) : null}
            {entry.on_behalf_of_name ? (
              <span className="ml-2">
                {t("activity.on_behalf_of")} {entry.on_behalf_of_name}
              </span>
            ) : null}
          </p>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          <p>{entry.ts ? new Date(entry.ts).toLocaleString() : t("activity.system")}</p>
          {entry.reason ? (
            <p className="mt-1">
              {t("activity.reason")}: {entry.reason}
            </p>
          ) : null}
        </div>
      </div>
      {hasValues ? (
        <div className="mt-3">
          <Button variant="outline" onClick={() => setShowChanges((open) => !open)}>
            {t("activity.changes")}
          </Button>
          {showChanges ? <ChangesTable entry={entry} /> : null}
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">{t("activity.no_changes")}</p>
      )}

      {entry.revertible ? (
        <div className="mt-3 border-t border-border pt-3">
          {!reverting ? (
            <Button
              variant="outline"
              data-testid={`activity-revert-${entry.seq}`}
              onClick={() => setReverting(true)}
            >
              {isRestore ? t("activity.restore") : t("activity.revert")}
            </Button>
          ) : (
            <div className="space-y-2">
              <label className="block text-sm">
                <span className="text-muted-foreground">{t("activity.reason")}</span>
                <Input
                  data-testid={`activity-reason-${entry.seq}`}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
              </label>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <div className="flex gap-2">
                <Button
                  data-testid={`activity-confirm-${entry.seq}`}
                  disabled={busy || !reason.trim()}
                  onClick={() => void submitRevert()}
                >
                  {isRestore ? t("activity.restore") : t("activity.revert")}
                </Button>
                <Button variant="ghost" onClick={() => setReverting(false)}>
                  {t("common.cancel")}
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function ActivityPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const allowed = hasPermission(user?.permissions, "audit.activity.view");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);

  const options = useQuery({
    queryKey: ["activity-options"],
    queryFn: () => api.get<ActivityOptions>("/api/v1/audit/activity/options"),
    enabled: allowed,
    retry: false,
  });

  const activity = useQuery({
    queryKey: ["activity", applied],
    queryFn: () => api.get<ActivityList>(`/api/v1/audit/activity${buildQuery(applied)}`),
    enabled: allowed,
    retry: false,
  });

  if (!allowed) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("activity.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive" data-testid="activity-permission">
            {t("activity.permission_denied")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const set = (field: keyof Filters) => (value: string) =>
    setFilters((current) => ({ ...current, [field]: value }));

  const apply = (event: FormEvent) => {
    event.preventDefault();
    setApplied(filters);
  };

  const clear = () => {
    setFilters(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
  };

  const items = activity.data?.items ?? [];

  return (
    <div className="space-y-5" data-testid="activity-page">
      <div>
        <h1 className="text-2xl font-semibold">{t("activity.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("activity.intro")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("activity.filters")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-3" onSubmit={apply}>
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("activity.user")}</span>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                data-testid="activity-filter-actor"
                value={filters.actor}
                onChange={(event) => set("actor")(event.target.value)}
              >
                <option value="">{t("activity.all_users")}</option>
                {(options.data?.actors ?? []).map((actor) => (
                  <option key={actor.id} value={actor.id}>
                    {actor.name ?? actor.id}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("activity.module")}</span>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                data-testid="activity-filter-module"
                value={filters.module}
                onChange={(event) => set("module")(event.target.value)}
              >
                <option value="">{t("activity.all_modules")}</option>
                {(options.data?.modules ?? []).map((key) => (
                  <option key={key} value={key}>
                    {moduleLabel(t, key)}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("activity.action")}</span>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                data-testid="activity-filter-action"
                value={filters.action}
                onChange={(event) => set("action")(event.target.value)}
              >
                <option value="">{t("activity.all_actions")}</option>
                {(options.data?.actions ?? []).map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("activity.entity_type")}</span>
              <Input
                data-testid="activity-filter-entity-type"
                value={filters.entityType}
                onChange={(event) => set("entityType")(event.target.value)}
              />
            </label>

            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">{t("activity.entity_id")}</span>
              <Input
                data-testid="activity-filter-entity-id"
                value={filters.entityId}
                onChange={(event) => set("entityId")(event.target.value)}
              />
            </label>

            <div className="grid grid-cols-2 gap-3">
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">{t("activity.date_from")}</span>
                <Input
                  type="date"
                  data-testid="activity-filter-from"
                  value={filters.from}
                  onChange={(event) => set("from")(event.target.value)}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">{t("activity.date_to")}</span>
                <Input
                  type="date"
                  data-testid="activity-filter-to"
                  value={filters.to}
                  onChange={(event) => set("to")(event.target.value)}
                />
              </label>
            </div>

            <div className="flex items-end gap-2 md:col-span-3">
              <Button type="submit" data-testid="activity-apply">
                {t("activity.apply")}
              </Button>
              <Button type="button" variant="outline" data-testid="activity-clear" onClick={clear}>
                {t("activity.clear")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("activity.title")}</CardTitle>
          <CardDescription data-testid="activity-count">
            {t("activity.showing", { count: items.length })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {activity.isPending ? (
            <p className="text-sm text-muted-foreground">{t("activity.loading")}</p>
          ) : activity.isError ? (
            <p className="text-sm text-destructive">{t("common.error")}</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="activity-empty">
              {t("activity.empty")}
            </p>
          ) : (
            <div>
              {items.map((entry) => (
                <EntryCard key={entry.seq} entry={entry} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
