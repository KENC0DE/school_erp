import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { useT } from "../i18n";
import { api, API_PREFIX } from "../lib/api";
import type { School, SchoolsResponse } from "../lib/types";

export function SchoolsPage() {
  const t = useT();
  const [schools, setSchools] = useState<School[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<SchoolsResponse>(`${API_PREFIX}/schools`);
      setSchools(response.items);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : t("controller.common.error"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-6" data-testid="schools-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">{t("controller.schools.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("controller.schools.description")}</p>
      </header>

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

      {!loading && !error && schools.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("controller.schools.empty")}</p>
      ) : null}

      <ul className="flex flex-col gap-3">
        {schools.map((school) => (
          <li
            key={school.id}
            data-testid={`school-row-${school.school_code}`}
            className="flex flex-col justify-between gap-4 rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm sm:flex-row sm:items-start"
          >
            <div className="min-w-0">
              <Link
                to={`/schools/${school.id}`}
                className="text-base font-semibold hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {school.name}
              </Link>
              <div className="mt-0.5 text-sm text-muted-foreground" data-testid="school-code">
                {school.school_code}
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {school.modules.map((module) => (
                  <Badge key={module}>{module}</Badge>
                ))}
              </div>
            </div>
            <div className="flex shrink-0 flex-row items-center gap-2 sm:flex-col sm:items-end">
              <StatusBadge status={school.status} testId={`school-status-${school.school_code}`} />
              <Badge>
                {t(
                  school.modules.length === 1
                    ? "controller.schools.modulesOne"
                    : "controller.schools.modules",
                  { count: school.modules.length },
                )}
              </Badge>              <Badge>
                {t(
                  school.enrolled
                    ? "controller.schools.enrolled"
                    : "controller.schools.notEnrolled",
                )}
              </Badge>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
