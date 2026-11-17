import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { api } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

interface PermissionGrant {
  permission: string;
  scope: string;
}

interface PermissionDeclaration {
  code: string;
  module: string;
  scopes: string[];
  label_key: string;
}

interface PermissionsResponse {
  items: PermissionDeclaration[];
  next_cursor: string | null;
  can_grant: string[];
}

interface RoleItem {
  id: string;
  key: string;
  name: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
  require_totp: boolean;
  permissions: PermissionGrant[];
}

interface RoleList {
  items: RoleItem[];
  next_cursor: string | null;
}

const WILDCARD = "*";
const pairKey = (permission: string, scope: string) => `${permission}\u0000${scope}`;

const ERROR_KEYS: Record<string, string> = {
  CANNOT_GRANT: "error.cannot_grant",
  PERMISSION_DENIED: "error.permission_denied",
  INVALID_SCOPE: "error.invalid_scope",
  UNKNOWN_PERMISSION: "error.unknown_permission",
  ROLE_EXISTS: "error.role_exists",
  ROLE_INACTIVE: "error.role_inactive",
};

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    const key = ERROR_KEYS[error.code];
    if (key) return key;
  }
  return fallback;
}

function hasPermission(permissions: string[] | undefined, permission: string): boolean {
  return Boolean(permissions?.includes(WILDCARD) || permissions?.includes(permission));
}

function moduleLabel(translate: (key: string) => string, module: string): string {
  const key = `settings.module.${module}`;
  const label = translate(key);
  return label === key ? module : label;
}

export function RolesPage() {
  const { t } = useI18n();
  const { user, refresh: refreshUser } = useAuth();
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [fullAccess, setFullAccess] = useState(false);
  const [pairs, setPairs] = useState<Set<string>>(new Set());
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [key, setKey] = useState("");
  const [requireTotp, setRequireTotp] = useState(false);
  const [saved, setSaved] = useState(false);

  const canManage = hasPermission(user?.permissions, "roles.manage");

  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<RoleList>("/api/v1/rbac/roles"),
    retry: false,
  });
  const permissions = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api.get<PermissionsResponse>("/api/v1/rbac/permissions"),
    retry: false,
  });

  const selected = roles.data?.items.find((role) => role.id === selectedId) ?? null;

  useEffect(() => {
    if (selectedId || creating || !roles.data) return;
    const first = roles.data.items[0];
    if (first) setSelectedId(first.id);
  }, [roles.data, selectedId, creating]);

  useEffect(() => {
    if (!selected) return;
    setName(selected.name);
    setDescription(selected.description ?? "");
    setRequireTotp(selected.require_totp);
    setFullAccess(selected.permissions.some((grant) => grant.permission === WILDCARD));
    setPairs(
      new Set(
        selected.permissions
          .filter((grant) => grant.permission !== WILDCARD)
          .map((grant) => pairKey(grant.permission, grant.scope)),
      ),
    );
  }, [selected]);

  const grouped = useMemo(() => {
    const groups = new Map<string, PermissionDeclaration[]>();
    for (const declaration of permissions.data?.items ?? []) {
      const current = groups.get(declaration.module) ?? [];
      current.push(declaration);
      groups.set(declaration.module, current);
    }
    return [...groups.entries()].sort(([left], [right]) => {
      if (left === "core") return -1;
      if (right === "core") return 1;
      return left.localeCompare(right);
    });
  }, [permissions.data]);

  const selectedPairs = useMemo(
    () =>
      [...pairs]
        .map((value) => value.split("\u0000") as [string, string])
        .sort(([leftPermission, leftScope], [rightPermission, rightScope]) =>
          `${leftPermission}|${leftScope}`.localeCompare(`${rightPermission}|${rightScope}`),
        ),
    [pairs],
  );

  function togglePair(permission: string, scope: string) {
    setPairs((current) => {
      const next = new Set(current);
      const value = pairKey(permission, scope);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
    setSaved(false);
  }

  function startCreate() {
    setCreating(true);
    setSelectedId(null);
    setName("");
    setDescription("");
    setKey("");
    setRequireTotp(false);
    setFullAccess(false);
    setPairs(new Set());
    setSaved(false);
  }

  const save = useMutation({
    mutationFn: async (): Promise<RoleItem> => {
      const grants: PermissionGrant[] = fullAccess
        ? [{ permission: WILDCARD, scope: "all" }]
        : selectedPairs.map(([permission, scope]) => ({ permission, scope }));
      if (creating) {
        return api.post<RoleItem>("/api/v1/rbac/roles", {
          key,
          name,
          description: description || null,
          require_totp: requireTotp,
          permissions: grants,
        });
      }
      if (!selected) throw new Error("No role selected");
      await api.patch<RoleItem>(`/api/v1/rbac/roles/${selected.id}`, {
        name,
        description: description || null,
        require_totp: requireTotp,
      });
      return api.put<RoleItem>(`/api/v1/rbac/roles/${selected.id}/permissions`, {
        permissions: grants,
      });
    },
    onSuccess: async (role) => {
      setCreating(false);
      setSelectedId(role.id);
      setSaved(true);
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      await queryClient.invalidateQueries({ queryKey: ["permissions"] });
      await queryClient.invalidateQueries({ queryKey: ["navigation"] });
      await refreshUser();
    },
  });

  const status = useMutation({
    mutationFn: ({ role, active }: { role: RoleItem; active: boolean }) =>
      active
        ? api.patch<RoleItem>(`/api/v1/rbac/roles/${role.id}`, { is_active: true })
        : api.del<RoleItem>(`/api/v1/rbac/roles/${role.id}`),
    onSuccess: async (_role, variables) => {
      setSelectedId(variables.role.id);
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      await queryClient.invalidateQueries({ queryKey: ["navigation"] });
      await refreshUser();
    },
  });

  const busy = save.isPending || status.isPending;
  const error = save.error ?? status.error;
  const errorMessage = error
    ? t(errorText(error, error instanceof ApiRequestError ? error.message : t("common.error")))
    : null;

  return (
    <div className="space-y-5" data-testid="roles-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("roles.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("roles.intro")}</p>
        </div>
        {canManage ? (
          <Button type="button" variant="outline" onClick={startCreate} disabled={busy}>
            {t("roles.new")}
          </Button>
        ) : null}
      </div>

      {roles.isLoading ? <p className="text-sm text-muted-foreground">{t("common.loading")}</p> : null}
      {roles.isError ? <p className="text-sm text-destructive">{t("common.error")}</p> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>{t("roles.title")}</CardTitle>
            <CardDescription>{t("roles.select")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {[...(roles.data?.items ?? [])]
              .sort((left, right) => left.key.localeCompare(right.key))
              .map((role) => (
                <button
                  key={role.id}
                  type="button"
                  data-testid={`role-row-${role.key}`}
                  aria-current={role.id === selectedId}
                  onClick={() => {
                    setCreating(false);
                    setSelectedId(role.id);
                    setSaved(false);
                  }}
                  className={`flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition ${
                    role.id === selectedId
                      ? "bg-muted font-medium text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate">{role.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">{role.key}</span>
                  </span>
                  <span className="flex shrink-0 gap-1">
                    {role.is_system ? <Badge>{t("roles.system")}</Badge> : null}
                    {!role.is_active ? <Badge>{t("roles.inactive")}</Badge> : null}
                  </span>
                </button>
              ))}
          </CardContent>
        </Card>

        <Card>
          {creating ? (
            <CardHeader>
              <CardTitle>{t("roles.new")}</CardTitle>
              <CardDescription>{t("roles.key_hint")}</CardDescription>
            </CardHeader>
          ) : selected ? (
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>{selected.name}</CardTitle>
                {selected.is_system ? <Badge>{t("roles.system")}</Badge> : null}
                {!selected.is_active ? <Badge>{t("roles.inactive")}</Badge> : null}
              </div>
              <CardDescription>
                {t("roles.permission_count", {
                  count: fullAccess ? permissions.data?.items.length ?? 0 : pairs.size,
                })}
              </CardDescription>
            </CardHeader>
          ) : (
            <CardContent className="pt-5 text-sm text-muted-foreground">{t("roles.empty")}</CardContent>
          )}

          {creating || selected ? (
            <CardContent className="space-y-5">
              <div className="grid gap-3 md:grid-cols-2">
                {creating ? (
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">{t("roles.key")}</span>
                    <Input
                      aria-label={t("roles.key")}
                      value={key}
                      pattern="[a-z][a-z0-9_]{1,59}"
                      required
                      disabled={!canManage || busy}
                      onChange={(event) => {
                        setKey(event.target.value);
                        setSaved(false);
                      }}
                    />
                  </label>
                ) : null}
                <label className="space-y-1 text-sm">
                  <span className="font-medium">{t("roles.name")}</span>
                  <Input
                    aria-label={t("roles.name")}
                    value={name}
                    required
                    disabled={!canManage || busy}
                    onChange={(event) => {
                      setName(event.target.value);
                      setSaved(false);
                    }}
                  />
                </label>
                <label className="space-y-1 text-sm md:col-span-2">
                  <span className="font-medium">{t("roles.description")}</span>
                  <Input
                    aria-label={t("roles.description")}
                    value={description}
                    disabled={!canManage || busy}
                    onChange={(event) => {
                      setDescription(event.target.value);
                      setSaved(false);
                    }}
                  />
                </label>
              </div>

              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={requireTotp}
                  disabled={!canManage || busy}
                  onChange={(event) => {
                    setRequireTotp(event.target.checked);
                    setSaved(false);
                  }}
                />
                <span>{t("roles.requires_totp")}</span>
              </label>

              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={fullAccess}
                  disabled={!canManage || busy}
                  onChange={(event) => {
                    setFullAccess(event.target.checked);
                    setSaved(false);
                  }}
                />
                <span>{t("roles.full_access")}</span>
              </label>

              {!fullAccess ? (
                <div className="space-y-4">
                  {permissions.isLoading ? (
                    <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
                  ) : null}
                  {grouped.map(([module, declarations]) => (
                    <section key={module} className="space-y-2">
                      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        {moduleLabel(t, module)}
                      </h2>
                      <div className="divide-y divide-border rounded-md border border-border">
                        {declarations.map((declaration) => (
                          <div
                            key={declaration.code}
                            className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                          >
                            <span className="min-w-0 text-sm">
                              <span className="block">{t(declaration.label_key)}</span>
                              <span className="block font-mono text-xs text-muted-foreground">
                                {declaration.code}
                              </span>
                            </span>
                            <span className="flex flex-wrap gap-2">
                              {declaration.scopes.map((scope) => {
                                const value = pairKey(declaration.code, scope);
                                return (
                                  <label
                                    key={scope}
                                    className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs"
                                  >
                                    <input
                                      type="checkbox"
                                      data-testid={`permission-${declaration.code}-${scope}`}
                                      aria-label={`${t(declaration.label_key)} (${t(`rbac.scope.${scope}`)})`}
                                      checked={pairs.has(value)}
                                      disabled={!canManage || busy}
                                      onChange={() => togglePair(declaration.code, scope)}
                                    />
                                    <span>{t(`rbac.scope.${scope}`)}</span>
                                  </label>
                                );
                              })}
                            </span>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              ) : null}

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  data-testid="roles-save"
                  disabled={!canManage || busy || (!creating && !selected)}
                  onClick={() => save.mutate()}
                >
                  {creating ? t("roles.create") : t("roles.save")}
                </Button>
                {selected && !creating ? (
                  <Button
                    type="button"
                    variant={selected.is_active ? "destructive" : "outline"}
                    disabled={!canManage || busy}
                    onClick={() => status.mutate({ role: selected, active: !selected.is_active })}
                  >
                    {selected.is_active ? t("roles.deactivate") : t("roles.reactivate")}
                  </Button>
                ) : null}
                {saved ? <span className="text-sm text-primary">{t("roles.saved")}</span> : null}
                {errorMessage ? (
                  <span role="alert" className="text-sm text-destructive">
                    {errorMessage}
                  </span>
                ) : null}
              </div>
            </CardContent>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
