import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { api } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

interface UserItem {
  id: string;
  email: string;
  phone: string | null;
  display_name: string;
  is_active: boolean;
  locale: string;
  must_change_password: boolean;
  last_login_at: string | null;
  locked_until: string | null;
  roles: string[];
}

interface UserList {
  items: UserItem[];
  next_cursor: string | null;
}

interface RoleItem {
  id: string;
  key: string;
  name: string;
  is_active: boolean;
}

interface RoleList {
  items: RoleItem[];
  next_cursor: string | null;
}

interface EffectivePermissions {
  user_id: string;
  roles: string[];
  effective: { permissions: string[]; scopes: Record<string, string[]> };
}

const WILDCARD = "*";

const ERROR_KEYS: Record<string, string> = {
  CANNOT_GRANT: "error.cannot_grant",
  PERMISSION_DENIED: "error.permission_denied",
  EMAIL_EXISTS: "error.email_exists",
  PHONE_EXISTS: "error.phone_exists",
  CANNOT_DEACTIVATE_SELF: "error.cannot_deactivate_self",
  ROLE_INACTIVE: "error.role_inactive",
  ROLE_NOT_ASSIGNED: "error.role_not_assigned",
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

export function UsersPage() {
  const { t, locale } = useI18n();
  const { user, refresh: refreshUser } = useAuth();
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inviting, setInviting] = useState(false);
  const [draftRoles, setDraftRoles] = useState<Set<string>>(new Set());
  const [rolesSaved, setRolesSaved] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [inviteRoles, setInviteRoles] = useState<Set<string>>(new Set());
  const [inviteLink, setInviteLink] = useState<string | null>(null);

  const canManageUsers = hasPermission(user?.permissions, "users.manage");
  const canViewRoles = hasPermission(user?.permissions, "roles.view");
  const canManageRoles = hasPermission(user?.permissions, "roles.manage");

  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserList>("/api/v1/auth/users"),
    retry: false,
  });
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<RoleList>("/api/v1/rbac/roles"),
    enabled: canViewRoles,
    retry: false,
  });

  const selected = users.data?.items.find((item) => item.id === selectedId) ?? null;
  const activeRoles = (roles.data?.items ?? []).filter((role) => role.is_active);

  useEffect(() => {
    setDraftRoles(new Set(selected?.roles ?? []));
  }, [selected]);

  const effective = useQuery({
    queryKey: ["user-permissions", selectedId],
    queryFn: () => api.get<EffectivePermissions>(`/api/v1/rbac/users/${selectedId}/permissions`),
    enabled: Boolean(selectedId) && canViewRoles,
    retry: false,
  });

  async function refreshAfterChange() {
    await queryClient.invalidateQueries({ queryKey: ["users"] });
    await queryClient.invalidateQueries({ queryKey: ["user-permissions"] });
    await queryClient.invalidateQueries({ queryKey: ["navigation"] });
    await refreshUser();
  }

  const invite = useMutation({
    mutationFn: () =>
      api.post<UserItem & { invitation_sent: boolean; invitation_link?: string }>("/api/v1/auth/users", {
        email,
        display_name: displayName,
        phone: phone || null,
        locale,
        role_ids: [...inviteRoles],
      }),
    onSuccess: async (created) => {
      setInviteLink(created.invitation_link ?? null);
      setEmail("");
      setDisplayName("");
      setPhone("");
      setInviteRoles(new Set());
      setInviting(false);
      await refreshAfterChange();
    },
  });

  const status = useMutation({
    mutationFn: ({ target, active }: { target: UserItem; active: boolean }) =>
      api.patch<UserItem>(`/api/v1/auth/users/${target.id}`, { is_active: active }),
    onSuccess: async () => {
      await refreshAfterChange();
    },
  });

  const saveRoles = useMutation({
    mutationFn: async (target: UserItem) => {
      const current = new Set(target.roles);
      const wanted = draftRoles;
      for (const role of activeRoles) {
        if (wanted.has(role.key) && !current.has(role.key)) {
          await api.post(`/api/v1/rbac/users/${target.id}/roles`, { role_id: role.id });
        }
        if (!wanted.has(role.key) && current.has(role.key)) {
          await api.del(`/api/v1/rbac/users/${target.id}/roles/${role.id}`);
        }
      }
    },
    onSuccess: async () => {
      setRolesSaved(true);
      await refreshAfterChange();
    },
  });

  function toggleDraftRole(roleKey: string) {
    setDraftRoles((current) => {
      const next = new Set(current);
      if (next.has(roleKey)) next.delete(roleKey);
      else next.add(roleKey);
      return next;
    });
    setRolesSaved(false);
  }

  function toggleInviteRole(roleId: string) {
    setInviteRoles((current) => {
      const next = new Set(current);
      if (next.has(roleId)) next.delete(roleId);
      else next.add(roleId);
      return next;
    });
  }

  function startInvite() {
    setInviting(true);
    setSelectedId(null);
    setInviteLink(null);
    setRolesSaved(false);
    invite.reset();
  }

  function submitInvite(event: FormEvent) {
    event.preventDefault();
    if (email.trim() && displayName.trim()) invite.mutate();
  }

  const busy = invite.isPending || status.isPending || saveRoles.isPending;
  const error = invite.error ?? status.error ?? saveRoles.error;
  const errorMessage = error
    ? t(errorText(error, error instanceof ApiRequestError ? error.message : t("common.error")))
    : null;

  return (
    <div className="space-y-5" data-testid="users-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("users.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("users.intro")}</p>
        </div>
        {canManageUsers ? (
          <Button type="button" data-testid="invite-open" variant="outline" onClick={startInvite} disabled={busy}>
            {t("users.invite")}
          </Button>
        ) : null}
      </div>

      {users.isLoading ? <p className="text-sm text-muted-foreground">{t("common.loading")}</p> : null}
      {users.isError ? <p className="text-sm text-destructive">{t("common.error")}</p> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>{t("users.title")}</CardTitle>
            <CardDescription>{t("users.intro")}</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[34rem] text-left text-sm">
              <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-2 py-2 font-medium">{t("users.name")}</th>
                  <th className="px-2 py-2 font-medium">{t("users.roles")}</th>
                  <th className="px-2 py-2 font-medium">{t("users.status")}</th>
                  <th className="px-2 py-2 font-medium">{t("users.last_login")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(users.data?.items ?? []).map((item) => (
                  <tr
                    key={item.id}
                    data-testid={`user-row-${item.email}`}
                    aria-current={item.id === selectedId}
                    className={`cursor-pointer transition hover:bg-muted ${
                      item.id === selectedId ? "bg-muted" : ""
                    }`}
                    onClick={() => {
                      setInviting(false);
                      setSelectedId(item.id);
                      setRolesSaved(false);
                    }}
                  >
                    <td className="px-2 py-3">
                      <span className="block font-medium">{item.display_name}</span>
                      <span className="block text-xs text-muted-foreground">{item.email}</span>
                    </td>
                    <td className="px-2 py-3">
                      <span className="flex flex-wrap gap-1">
                        {item.roles.length === 0 ? (
                          <span className="text-xs text-muted-foreground">{t("users.no_roles")}</span>
                        ) : (
                          item.roles.map((role) => <Badge key={role}>{role}</Badge>)
                        )}
                      </span>
                    </td>
                    <td className="px-2 py-3">
                      <Badge>{item.is_active ? t("users.active") : t("users.inactive")}</Badge>
                      {item.id === user?.id ? (
                        <span className="ml-1 text-xs text-muted-foreground">({t("users.you")})</span>
                      ) : null}
                    </td>
                    <td className="px-2 py-3 text-xs text-muted-foreground">
                      {item.last_login_at ? new Date(item.last_login_at).toLocaleString(locale) : t("users.never")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card className="h-fit">
          {inviting ? (
            <>
              <CardHeader>
                <CardTitle>{t("users.invite")}</CardTitle>
                <CardDescription>{t("users.invite_hint")}</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-3" onSubmit={submitInvite}>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">{t("users.name")}</span>
                    <Input
                      aria-label={t("users.name")}
                      data-testid="invite-name"
                      value={displayName}
                      required
                      disabled={busy}
                      onChange={(event) => setDisplayName(event.target.value)}
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">{t("auth.email")}</span>
                    <Input
                      aria-label={t("auth.email")}
                      data-testid="invite-email"
                      type="email"
                      value={email}
                      required
                      disabled={busy}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">{t("users.phone")}</span>
                    <Input
                      aria-label={t("users.phone")}
                      value={phone}
                      disabled={busy}
                      onChange={(event) => setPhone(event.target.value)}
                    />
                  </label>
                  {canManageRoles ? (
                    <fieldset className="space-y-2">
                      <legend className="text-sm font-medium">{t("users.roles")}</legend>
                      <div className="flex flex-wrap gap-2">
                        {activeRoles.map((role) => (
                          <label
                            key={role.id}
                            className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs"
                          >
                            <input
                              type="checkbox"
                              data-testid={`invite-role-${role.key}`}
                              checked={inviteRoles.has(role.id)}
                              disabled={busy}
                              onChange={() => toggleInviteRole(role.id)}
                            />
                            <span>{role.name}</span>
                          </label>
                        ))}
                      </div>
                    </fieldset>
                  ) : null}
                  <div className="flex flex-wrap items-center gap-2">
                    <Button type="submit" data-testid="invite-submit" disabled={busy}>
                      {t("users.create")}
                    </Button>
                    <Button type="button" variant="ghost" onClick={() => setInviting(false)} disabled={busy}>
                      {t("common.cancel")}
                    </Button>
                  </div>
                  {invite.isSuccess ? <p className="text-sm text-primary">{t("users.invited")}</p> : null}
                  {inviteLink ? (
                    <p className="break-all text-xs text-muted-foreground">
                      {t("users.invite_link")}: <span className="font-mono">{inviteLink}</span>
                    </p>
                  ) : null}
                  {errorMessage ? (
                    <p role="alert" className="text-sm text-destructive">
                      {errorMessage}
                    </p>
                  ) : null}
                </form>
              </CardContent>
            </>
          ) : selected ? (
            <>
              <CardHeader>
                <CardTitle>{selected.display_name}</CardTitle>
                <CardDescription>{selected.email}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{selected.is_active ? t("users.active") : t("users.inactive")}</Badge>
                  {selected.must_change_password ? <Badge>{t("auth.password")}</Badge> : null}
                  {canManageUsers ? (
                    <Button
                      type="button"
                      data-testid="user-toggle-active"
                      variant={selected.is_active ? "destructive" : "outline"}
                      disabled={busy || selected.id === user?.id}
                      onClick={() => status.mutate({ target: selected, active: !selected.is_active })}
                    >
                      {selected.is_active ? t("users.deactivate") : t("users.reactivate")}
                    </Button>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <h2 className="text-sm font-semibold">{t("users.manage_roles")}</h2>
                  {canManageRoles ? (
                    <div className="flex flex-wrap gap-2">
                      {activeRoles.map((role) => (
                        <label
                          key={role.id}
                          className="flex items-center gap-1 rounded border border-border px-2 py-1 text-xs"
                        >
                          <input
                            type="checkbox"
                            data-testid={`user-role-${role.key}`}
                            checked={draftRoles.has(role.key)}
                            disabled={busy}
                            onChange={() => toggleDraftRole(role.key)}
                          />
                          <span>{role.name}</span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {selected.roles.length ? selected.roles.join(", ") : t("users.no_roles")}
                    </p>
                  )}
                  {canManageRoles ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        data-testid="users-save-roles"
                        disabled={busy}
                        onClick={() => saveRoles.mutate(selected)}
                      >
                        {t("users.save_roles")}
                      </Button>
                      {rolesSaved ? <span className="text-sm text-primary">{t("users.roles_saved")}</span> : null}
                    </div>
                  ) : null}
                </div>

                {canViewRoles ? (
                  <div className="space-y-2">
                    <h2 className="text-sm font-semibold">{t("users.permissions")}</h2>
                    {effective.isLoading ? (
                      <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {(effective.data?.effective.permissions ?? []).map((permission) => (
                          <Badge key={permission}>{permission}</Badge>
                        ))}
                        {effective.data && effective.data.effective.permissions.length === 0 ? (
                          <span className="text-sm text-muted-foreground">{t("users.no_roles")}</span>
                        ) : null}
                      </div>
                    )}
                  </div>
                ) : null}
              </CardContent>
            </>
          ) : (
            <CardContent className="pt-5 text-sm text-muted-foreground">{t("users.select")}</CardContent>
          )}
          {!inviting && errorMessage ? (
            <CardContent>
              <p role="alert" className="text-sm text-destructive">
                {errorMessage}
              </p>
            </CardContent>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
