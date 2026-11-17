import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge } from "../components/ui/Badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { api } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { useI18n } from "../providers/I18nProvider";

interface ModuleDependency {
  key: string;
  name: string;
  available: boolean;
}

interface ModuleDependant {
  key: string;
  name: string;
  enabled: boolean;
}

interface ModuleItem {
  key: string;
  name: string;
  version: string;
  description: string;
  core: boolean;
  licensable: boolean;
  depends_on: string[];
  dependencies: ModuleDependency[];
  dependants: ModuleDependant[];
  blocked_by: string[];
  permitted: boolean;
  licensed: boolean;
  enabled: boolean;
  available: boolean;
}

interface ModuleList {
  items: ModuleItem[];
  next_cursor: string | null;
}

const WILDCARD = "*";

function hasPermission(permissions: string[] | undefined, permission: string): boolean {
  return Boolean(permissions?.includes(WILDCARD) || permissions?.includes(permission));
}

function moduleLabel(translate: (key: string) => string, item: ModuleItem): string {
  const key = `settings.module.${item.key}`;
  const label = translate(key);
  return label === key ? item.name : label;
}

function stateBadgeClass(on: boolean): string {
  return on ? "border-primary/40 text-foreground" : "text-muted-foreground";
}

function StateBadge({
  label,
  on,
  onText,
  offText,
  testId,
}: {
  label: string;
  on: boolean;
  onText: string;
  offText: string;
  testId: string;
}) {
  return (
    <span className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <Badge className={stateBadgeClass(on)} data-testid={testId}>
        {on ? onText : offText}
      </Badge>
    </span>
  );
}

function ModuleRow({
  item,
  canManage,
  busy,
  onToggle,
}: {
  item: ModuleItem;
  canManage: boolean;
  busy: boolean;
  onToggle: (item: ModuleItem, enabled: boolean) => void;
}) {
  const { t } = useI18n();
  const label = moduleLabel(t, item);
  const activeDependants = item.dependants.filter((dependant) => dependant.enabled);
  const blockedBy = item.dependencies.filter((dependency) => !dependency.available);
  const blockedEnable = !item.enabled && blockedBy.length > 0;
  const blockedDisable = item.enabled && activeDependants.length > 0;
  const disabled =
    item.core ||
    !canManage ||
    (!item.licensed && !item.enabled) ||
    busy ||
    blockedEnable ||
    blockedDisable;

  return (
    <div
      className="grid gap-4 border-b border-border py-5 last:border-0 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start"
      data-testid={`module-row-${item.key}`}
    >
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold">{label}</h3>
          <Badge>{t("modules.version", { version: item.version })}</Badge>
          {item.core ? <Badge>{t("modules.core")}</Badge> : null}
          {!item.licensable ? <Badge>{t("modules.not_licensable")}</Badge> : null}
        </div>
        {item.description ? (
          <p className="text-sm text-muted-foreground">{item.description}</p>
        ) : null}

        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <StateBadge
            label={t("modules.licensed")}
            on={item.licensed}
            onText={t("common.yes")}
            offText={t("common.no")}
            testId={`module-licensed-${item.key}`}
          />
          <StateBadge
            label={t("modules.enabled")}
            on={item.enabled}
            onText={t("common.yes")}
            offText={t("common.no")}
            testId={`module-enabled-${item.key}`}
          />
          <StateBadge
            label={t("modules.permitted")}
            on={item.permitted}
            onText={t("common.yes")}
            offText={t("common.no")}
            testId={`module-permitted-${item.key}`}
          />
          <StateBadge
            label={t("modules.available")}
            on={item.available}
            onText={t("common.yes")}
            offText={t("common.no")}
            testId={`module-available-${item.key}`}
          />
        </div>

        <div className="space-y-1 text-sm">
          <p className="text-muted-foreground">
            <span className="font-medium text-foreground">{t("modules.depends_on")}: </span>
            {item.dependencies.length === 0
              ? t("modules.no_dependencies")
              : item.dependencies
                  .map((dependency) =>
                    dependency.available
                      ? dependency.name
                      : t("modules.dependency_unavailable", { dependency: dependency.name }),
                  )
                  .join(", ")}
          </p>
          {item.dependants.length > 0 ? (
            <p className="text-muted-foreground">
              <span className="font-medium text-foreground">{t("modules.dependants")}: </span>
              {item.dependants.map((dependant) => dependant.name).join(", ")}
            </p>
          ) : null}
        </div>

        {item.core ? (
          <p className="text-xs text-muted-foreground">{t("modules.core_always_on")}</p>
        ) : null}
        {!item.licensed ? (
          <p className="text-xs text-muted-foreground">{t("modules.unlicensed_hint")}</p>
        ) : null}
        {!item.permitted ? (
          <p className="text-xs text-muted-foreground">{t("modules.not_permitted_hint")}</p>
        ) : null}
        {blockedEnable ? (
          <p className="text-xs text-destructive" data-testid={`module-blocked-${item.key}`}>
            {t("modules.dependency_blocked", {
              dependencies: blockedBy.map((dependency) => dependency.name).join(", "),
            })}
          </p>
        ) : null}
        {blockedDisable ? (
          <p className="text-xs text-destructive" data-testid={`module-dependants-${item.key}`}>
            {t("modules.dependants_blocked", {
              dependants: activeDependants.map((dependant) => dependant.name).join(", "),
            })}
          </p>
        ) : null}
      </div>

      <div className="flex items-center gap-3 lg:justify-end">
        <label className="text-sm text-muted-foreground" htmlFor={`module-toggle-${item.key}`}>
          {item.enabled ? t("common.enabled") : t("common.disabled")}
        </label>
        <input
          id={`module-toggle-${item.key}`}
          type="checkbox"
          role="switch"
          className="h-5 w-5 accent-primary"
          checked={item.enabled}
          disabled={disabled}
          data-testid={`module-toggle-${item.key}`}
          onChange={(event) => onToggle(item, event.target.checked)}
        />
      </div>
    </div>
  );
}

function toggleErrorMessage(error: unknown, translate: (key: string) => string): string | null {
  if (!(error instanceof ApiRequestError)) return null;
  if (error.code === "PERMISSION_DENIED") return translate("error.permission_denied");
  if (error.code === "MODULE_DISABLED") return translate("error.module_disabled");
  const details = (error.details ?? {}) as { dependency?: string; dependants?: string[] };
  if (details.dependency) {
    return translate("modules.dependency_disabled");
  }
  if (details.dependants?.length) {
    return translate("modules.dependants_enabled");
  }
  return translate("common.error");
}

export function ModulesPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const canManage = hasPermission(user?.permissions, "modules.manage");

  const modules = useQuery({
    queryKey: ["modules"],
    queryFn: () => api.get<ModuleList>("/api/v1/system/modules"),
    retry: false,
  });

  const toggle = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      api.put<ModuleItem>(`/api/v1/system/modules/${encodeURIComponent(key)}`, { enabled }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["modules"] });
      await queryClient.invalidateQueries({ queryKey: ["navigation"] });
      await queryClient.invalidateQueries({ queryKey: ["capabilities"] });
    },
  });

  const errorMessage = toggleErrorMessage(toggle.error, t);

  return (
    <div className="space-y-5" data-testid="modules-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("modules.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("modules.intro")}</p>
        </div>
        <Link
          to="/settings"
          className="text-sm font-medium text-muted-foreground hover:text-foreground hover:underline"
        >
          {t("modules.back")}
        </Link>
      </div>

      {!canManage ? (
        <p className="text-sm text-muted-foreground">{t("modules.read_only")}</p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("modules.title")}</CardTitle>
          <CardDescription>{t("modules.gates_hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          {modules.isLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : null}
          {modules.isError ? (
            <p className="text-sm text-destructive">{t("common.error")}</p>
          ) : null}
          {errorMessage ? (
            <p role="alert" className="pb-4 text-sm text-destructive">
              {errorMessage}
            </p>
          ) : null}
          {(modules.data?.items ?? []).map((item) => (
            <ModuleRow
              key={item.key}
              item={item}
              canManage={canManage}
              busy={toggle.isPending && toggle.variables?.key === item.key}
              onToggle={(module, enabled) => toggle.mutate({ key: module.key, enabled })}
            />
          ))}
        </CardContent>
      </Card>

      {canManage ? (
        <p className="text-xs text-muted-foreground">{t("modules.audit_hint")}</p>
      ) : null}
    </div>
  );
}
