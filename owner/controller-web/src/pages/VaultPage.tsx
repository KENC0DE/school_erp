import { useCallback, useEffect, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { useT } from "../i18n";
import { api, API_PREFIX } from "../lib/api";
import type {
  School,
  SchoolsResponse,
  VaultAlert,
  VaultAlertsResponse,
  VaultItem,
  VaultResponse,
  VaultStatusResponse,
} from "../lib/types";

function formatTimestamp(ts: VaultItem["ts"], fallback: string): string {
  if (ts === null || ts === undefined || ts === "") return fallback;
  const date = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  return date.toLocaleString();
}

function ChainSummary({ status }: { status: VaultStatusResponse | null }) {
  const t = useT();
  if (!status) return null;
  const rows = status.items ?? (status.school_id ? [status] : []);
  return (
    <div className="grid gap-2 md:grid-cols-2" data-testid="vault-chain-summary">
      {rows.map((row) => (
        <div
          key={row.school_id}
          className="rounded-md border border-border bg-card p-3 text-sm"
          data-testid={`vault-status-${row.school_id}`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">{row.school_name ?? row.school_id}</span>
            {row.ok ? (
              <Badge>{t("controller.vault.chain.ok")}</Badge>
            ) : (
              <Badge className="border-destructive bg-destructive text-destructive-foreground">
                {t("controller.vault.chain.broken")}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("controller.vault.statusLine", {
              entries: row.entries ?? 0,
              lastSeq: row.last_seq ?? 0,
              broken: row.broken_entries ?? 0,
            })}
          </p>
          {row.chain_head ? (
            <p className="mt-1 break-all font-mono text-[10px] text-muted-foreground">
              {row.chain_head}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function VaultPage() {
  const t = useT();
  const [schools, setSchools] = useState<School[]>([]);
  const [schoolId, setSchoolId] = useState("");
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [chainFilter, setChainFilter] = useState("");
  const [items, setItems] = useState<VaultItem[]>([]);
  const [status, setStatus] = useState<VaultStatusResponse | null>(null);
  const [alerts, setAlerts] = useState<VaultAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

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
      const params = new URLSearchParams({ limit: "100" });
      if (schoolId) params.set("school_id", schoolId);
      if (appliedQuery) params.set("q", appliedQuery);
      if (chainFilter) params.set("chain_ok", chainFilter);
      const response = await api.get<VaultResponse>(`${API_PREFIX}/vault?${params.toString()}`);
      setItems(response.items);
    } catch (err) {
      setError(message(err));
    } finally {
      setLoading(false);
    }
  }, [schoolId, appliedQuery, chainFilter, message]);

  const loadOversight = useCallback(async () => {
    const params = schoolId ? `?school_id=${encodeURIComponent(schoolId)}` : "";
    try {
      const [statusResponse, alertResponse] = await Promise.all([
        api.get<VaultStatusResponse>(`${API_PREFIX}/vault/status${params}`),
        api.get<VaultAlertsResponse>(`${API_PREFIX}/vault/alerts${params}`),
      ]);
      setStatus(statusResponse);
      setAlerts(alertResponse.items);
    } catch {
      // Oversight panels are supplementary; the entry list keeps its own error state.
    }
  }, [schoolId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void loadOversight();
  }, [loadOversight]);

  const scan = async () => {
    setScanning(true);
    try {
      const params = schoolId ? `?school_id=${encodeURIComponent(schoolId)}` : "";
      await api.post(`${API_PREFIX}/vault/scan${params}`);
      await loadOversight();
    } catch (err) {
      setError(message(err));
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="flex flex-col gap-6" data-testid="vault-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">{t("controller.vault.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("controller.vault.description")}</p>
      </header>

      <div className="grid gap-3 md:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_10rem_auto] md:items-end">
        <div>
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
        <div>
          <label htmlFor="vault-search" className="mb-1.5 block text-sm font-medium">
            {t("controller.vault.search")}
          </label>
          <Input
            id="vault-search"
            data-testid="vault-search"
            value={query}
            placeholder={t("controller.vault.searchPlaceholder")}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") setAppliedQuery(query.trim());
            }}
          />
        </div>
        <div>
          <label htmlFor="vault-chain-filter" className="mb-1.5 block text-sm font-medium">
            {t("controller.vault.chain")}
          </label>
          <Select
            id="vault-chain-filter"
            data-testid="vault-chain-filter"
            value={chainFilter}
            onChange={(event) => setChainFilter(event.target.value)}
          >
            <option value="">{t("controller.vault.chain.any")}</option>
            <option value="true">{t("controller.vault.chain.ok")}</option>
            <option value="false">{t("controller.vault.chain.broken")}</option>
          </Select>
        </div>
        <Button data-testid="vault-search-apply" onClick={() => setAppliedQuery(query.trim())}>
          {t("controller.vault.apply")}
        </Button>
      </div>

      <section className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">{t("controller.vault.health")}</h2>
          <Button variant="outline" data-testid="vault-scan" disabled={scanning} onClick={() => void scan()}>
            {scanning ? t("controller.vault.scanning") : t("controller.vault.scan")}
          </Button>
        </div>
        <ChainSummary status={status} />
        {alerts.length > 0 ? (
          <ul className="space-y-2" data-testid="vault-alerts">
            {alerts.map((alert) => (
              <li
                key={alert.id}
                className="rounded-md border border-destructive bg-card px-3 py-2 text-sm"
                data-testid={`vault-alert-${alert.id}`}
              >
                <span className="font-medium">{alert.school_name ?? alert.school_id}</span>
                <Badge className="ml-2 border-destructive text-destructive">{alert.kind}</Badge>
                <p className="text-muted-foreground">{alert.message}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground" data-testid="vault-alerts-empty">
            {t("controller.vault.noAlerts")}
          </p>
        )}
      </section>

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
