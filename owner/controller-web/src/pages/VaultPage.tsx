import { useCallback, useEffect, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { useT } from "../i18n";
import { api, API_PREFIX } from "../lib/api";
import type { School, SchoolsResponse, VaultItem, VaultResponse } from "../lib/types";

function formatTimestamp(ts: VaultItem["ts"], fallback: string): string {
  if (ts === null || ts === undefined || ts === "") return fallback;
  const date = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  return date.toLocaleString();
}

export function VaultPage() {
  const t = useT();
  const [schools, setSchools] = useState<School[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [items, setItems] = useState<VaultItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const message = useCallback(
    (err: unknown) =>
      err instanceof Error && err.message ? err.message : t("controller.common.error"),
    [t],
  );

  useEffect(() => {
    let cancelled = false;
    api
      .get<SchoolsResponse>(`${API_PREFIX}/schools`)
      .then((response) => {
        if (!cancelled) setSchools(response.items);
      })
      .catch(() => {
        // The filter degrades to "all schools"; the vault request reports errors.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query = schoolId ? `&school_id=${encodeURIComponent(schoolId)}` : "";
      const response = await api.get<VaultResponse>(
        `${API_PREFIX}/vault?limit=100${query}`,
      );
      setItems(response.items);
    } catch (err) {
      setError(message(err));
    } finally {
      setLoading(false);
    }
  }, [schoolId, message]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-6" data-testid="vault-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">{t("controller.vault.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("controller.vault.description")}</p>
      </header>

      <div className="w-full max-w-xs">
        <label htmlFor="vault-school-filter" className="mb-1.5 block text-sm font-medium">
          {t("controller.vault.schoolFilter")}
        </label>
        <Select
          id="vault-school-filter"
          value={schoolId}
          data-testid="vault-school-filter"
          onChange={(event) => setSchoolId(event.target.value)}
        >
          <option value="">{t("controller.vault.allSchools")}</option>
          {schools.map((school) => (
            <option key={school.id} value={school.id}>
              {school.name}
            </option>
          ))}
        </Select>
      </div>

      {error ? (
        <div role="alert" className="flex items-center justify-between gap-4 rounded-md border border-destructive bg-card p-4">
          <span className="text-sm text-destructive">{error}</span>
          <Button variant="outline" onClick={() => void load()}>
            {t("controller.common.retry")}
          </Button>
        </div>
      ) : null}

      {loading ? (
        <p role="status" className="text-sm text-muted-foreground">
          {t("controller.common.loading")}
        </p>
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("controller.vault.empty")}</p>
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <>
          <p className="text-xs text-muted-foreground">
            {t("controller.vault.limit", { count: items.length })}
          </p>
          <div className="overflow-x-auto rounded-lg border border-border bg-card">
            <table className="w-full min-w-[900px] border-collapse text-left text-sm" data-testid="vault-table">
              <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.school")}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.seq")}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.action")}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.module")}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.actor")}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.via")}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.entity")}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.time")}</th>
                  <th scope="col" className="px-3 py-2 font-medium">{t("controller.vault.column.chain")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.id}
                    data-testid={`vault-row-${item.id}`}
                    className="border-t border-border align-top"
                  >
                    <td className="px-3 py-2">{item.school_name ?? item.school_id}</td>
                    <td className="px-3 py-2 tabular-nums">{item.seq}</td>
                    <td className="px-3 py-2">{item.action ?? t("controller.common.none")}</td>
                    <td className="px-3 py-2">{item.module ?? t("controller.common.none")}</td>
                    <td className="px-3 py-2">
                      {item.actor_type ?? t("controller.common.none")}
                      {item.actor_id ? (
                        <span className="block text-xs text-muted-foreground">{item.actor_id}</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">
                      <Badge data-testid="vault-via">
                        {t("controller.vault.viaValue", {
                          via: item.via ?? t("controller.common.none"),
                        })}
                      </Badge>
                    </td>
                    <td className="px-3 py-2">
                      {item.entity_type ?? t("controller.common.none")}
                      {item.entity_id ? (
                        <span className="block text-xs text-muted-foreground">{item.entity_id}</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {formatTimestamp(item.ts, t("controller.common.none"))}
                    </td>
                    <td className="px-3 py-2">
                      {item.chain_ok ? (
                        <Badge data-testid="vault-chain-ok">
                          {t("controller.vault.chain.ok")}
                        </Badge>
                      ) : (
                        <Badge
                          className="border-destructive bg-destructive text-destructive-foreground"
                          data-testid="vault-chain-broken"
                        >
                          {t("controller.vault.chain.broken")}
                        </Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
