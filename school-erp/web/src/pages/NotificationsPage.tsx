import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { api } from "../lib/api";
import { useI18n } from "../providers/I18nProvider";

interface NotificationRow {
  id: string;
  template_key: string;
  category: string;
  title: string;
  body: string;
  params: Record<string, unknown>;
  link: string | null;
  channels: string[];
  read: boolean;
  read_at: string | null;
  created_at: string | null;
}

interface Inbox {
  items: NotificationRow[];
  unread: number;
  next_offset: number | null;
}

type Filter = "all" | "unread";

function formatDate(value: string | null, locale: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

export function NotificationsPage() {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");

  const inbox = useQuery({
    queryKey: ["notifications", filter],
    queryFn: () =>
      api.get<Inbox>(
        filter === "unread" ? "/api/v1/notifications?unread_only=true" : "/api/v1/notifications",
      ),
  });

  const markOne = useMutation({
    mutationFn: (id: string) => api.post<NotificationRow>(`/api/v1/notifications/${id}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const markAll = useMutation({
    mutationFn: () => api.post<{ updated: number }>("/api/v1/notifications/read-all"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const items = inbox.data?.items ?? [];
  const unread = inbox.data?.unread ?? 0;

  return (
    <div className="space-y-5" data-testid="notifications-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("notifications.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("notifications.intro")}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge data-testid="notifications-unread">
            {t("notifications.unread", { count: unread })}
          </Badge>
          <Button
            variant="outline"
            onClick={() => markAll.mutate()}
            disabled={markAll.isPending || unread === 0}
          >
            {t("notifications.mark_all_read")}
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2" role="group" aria-label={t("notifications.title")}>
        <Button
          variant={filter === "all" ? "default" : "outline"}
          onClick={() => setFilter("all")}
          aria-pressed={filter === "all"}
        >
          {t("notifications.all")}
        </Button>
        <Button
          variant={filter === "unread" ? "default" : "outline"}
          onClick={() => setFilter("unread")}
          aria-pressed={filter === "unread"}
        >
          {t("notifications.unread_only")}
        </Button>
      </div>

      {inbox.isLoading ? (
        <p className="text-sm text-muted-foreground">{t("notifications.loading")}</p>
      ) : null}

      {!inbox.isLoading && items.length === 0 ? (
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-muted-foreground">
              {filter === "unread" ? t("notifications.empty_unread") : t("notifications.empty")}
            </p>
          </CardContent>
        </Card>
      ) : null}

      <div className="space-y-3" data-testid="notifications-list">
        {items.map((item) => (
          <Card key={item.id} data-testid={`notification-${item.id}`}>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div className="min-w-0">
                <CardTitle className="text-base">{item.title}</CardTitle>
                <CardDescription>{formatDate(item.created_at, locale)}</CardDescription>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Badge>{t(`notifications.category.${item.category}`)}</Badge>
                {item.read ? <Badge>{t("notifications.read")}</Badge> : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="whitespace-pre-line text-sm">{item.body}</p>
              <div className="flex flex-wrap items-center gap-2">
                {item.link ? (
                  <a
                    className="text-sm font-medium text-primary underline-offset-4 hover:underline"
                    href={item.link}
                  >
                    {t("notifications.open_item")}
                  </a>
                ) : null}
                {!item.read ? (
                  <Button
                    variant="outline"
                    onClick={() => markOne.mutate(item.id)}
                    disabled={markOne.isPending}
                  >
                    {t("notifications.mark_read")}
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
