import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@erp/ui-web";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useI18n } from "../../providers/I18nProvider";
import { ACADEMICS, useLevels, useScope } from "./queries";

export function ScopePanel({ canManage }: { canManage: boolean }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const scope = useScope();
  const levels = useLevels(canManage);
  const [first, setFirst] = useState("0");
  const [last, setLast] = useState("12");
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (!scope.data) return;
    setFirst(String(scope.data.first_level));
    setLast(String(scope.data.last_level));
  }, [scope.data]);

  const save = useMutation({
    mutationFn: () =>
      api.put(`${ACADEMICS}/scope`, {
        first_level: Number(first),
        last_level: Number(last),
        reason: reason || null,
      }),
    onSuccess: () => {
      setReason("");
      void queryClient.invalidateQueries({ queryKey: ["academics"] });
    },
  });

  const options = levels.data?.items ?? [];
  const inScope = options.filter((level) => level.scope_level >= Number(first) && level.scope_level <= Number(last));
  const error = save.error instanceof ApiRequestError ? save.error.message : null;

  if (scope.isLoading) return <LoadingState label={t("common.loading")} />;
  if (scope.isError)
    return (
      <ErrorState
        title={t("common.error")}
        requestId={requestIdOf(scope.error)}
        requestIdLabel={t("common.request_id")}
        retry={
          <Button size="sm" variant="outline" onClick={() => void scope.refetch()}>
            {t("common.retry")}
          </Button>
        }
      />
    );

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>{t("academics.scope")}</CardTitle>
          <CardDescription>{t("academics.scope.hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("academics.scope.first_level")}</span>
              <select
                aria-label={t("academics.scope.first_level")}
                className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={first}
                disabled={!canManage}
                onChange={(event) => setFirst(event.target.value)}
              >
                {options.map((level) => (
                  <option key={level.id} value={level.scope_level}>
                    {level.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium">{t("academics.scope.last_level")}</span>
              <select
                aria-label={t("academics.scope.last_level")}
                className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={last}
                disabled={!canManage}
                onChange={(event) => setLast(event.target.value)}
              >
                {options.map((level) => (
                  <option key={level.id} value={level.scope_level}>
                    {level.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            <Badge>
              {t("academics.scope.levels_count", { count: inScope.length })}
            </Badge>
            <Badge>{t("academics.scope.stages_count", { count: scope.data?.stage_count ?? 0 })}</Badge>
          </div>
          {canManage ? (
            <>
              <Input
                aria-label={t("academics.scope.reason")}
                placeholder={t("academics.scope.reason")}
                value={reason}
                maxLength={500}
                onChange={(event) => setReason(event.target.value)}
              />
              <Button onClick={() => save.mutate()} disabled={save.isPending}>
                {save.isPending ? t("academics.scope.saving") : t("academics.scope.save")}
              </Button>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">{t("academics.setup.manage_hint")}</p>
          )}
          {save.isSuccess ? <p className="text-sm text-primary">{t("academics.scope.saved")}</p> : null}
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("academics.levels")}</CardTitle>
          <CardDescription>{t("academics.scope.starter_hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="divide-y divide-border text-sm">
            {inScope.map((level) => (
              <li key={level.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="font-medium">{level.name}</span>
                <span className="flex items-center gap-2">
                  {level.is_starter && !level.is_verified ? (
                    <Badge>{t("academics.verify_hint")}</Badge>
                  ) : null}
                  <span className="text-xs text-muted-foreground">{level.name_am}</span>
                </span>
              </li>
            ))}
            {inScope.length === 0 ? (
              <EmptyState title={t("academics.empty.levels")} />
            ) : null}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
