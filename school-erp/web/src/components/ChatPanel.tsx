import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, type Navigation } from "../lib/api";
import { useI18n } from "../providers/I18nProvider";
import { Button } from "./ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/Card";

interface Tool {
  key: string;
  description: string;
  risk: string;
  requires_confirmation: boolean;
}

interface ChatResponse {
  reply: string;
  tools: Tool[];
  configured: boolean;
  note_key: string;
}

export function ChatPanel() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState<ChatResponse | null>(null);

  const nav = useQuery({
    queryKey: ["navigation"],
    queryFn: () => api.get<Navigation>("/api/v1/auth/me/navigation"),
  });
  const canUseAi = nav.data?.modules.includes("ai") || true;

  const chat = useMutation({
    mutationFn: (text: string) => api.post<ChatResponse>("/api/v1/ai/chat", { message: text }),
    onSuccess: (data) => setAnswer(data),
  });

  if (!canUseAi) return null;

  return (
    <div className="fixed bottom-6 right-6 z-40 w-[min(24rem,calc(100vw-3rem))]">
      {open ? (
        <Card className="shadow-xl">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{t("ai.title")}</CardTitle>
            <Button variant="ghost" onClick={() => setOpen(false)} aria-label={t("common.cancel")}>
              ×
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (message.trim()) chat.mutate(message.trim());
              }}
            >
              <input
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder={t("ai.placeholder")}
                className="h-9 flex-1 rounded-md border border-input bg-background px-2 text-sm"
              />
              <Button type="submit" disabled={chat.isPending}>
                {t("ai.send")}
              </Button>
            </form>
            {answer ? (
              <div className="space-y-2 text-sm">
                <p className="rounded-md bg-muted p-2">{answer.reply}</p>
                <p className="font-medium">{t("ai.tools")}</p>
                <ul className="space-y-1">
                  {answer.tools.map((tool) => (
                    <li key={tool.key} className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs">{tool.key}</span>
                      <span className="text-xs text-muted-foreground">{tool.risk}</span>
                    </li>
                  ))}
                  {answer.tools.length === 0 && (
                    <li className="text-xs text-muted-foreground">{t("ai.no_tools")}</li>
                  )}
                </ul>
                <p className="text-xs text-muted-foreground">{t("ai.stub_note")}</p>
              </div>
            ) : null}
            {chat.isError ? <p className="text-xs text-destructive">{t("common.error")}</p> : null}
          </CardContent>
        </Card>
      ) : (
        <Button className="rounded-full shadow-lg" onClick={() => setOpen(true)}>
          {t("ai.title")}
        </Button>
      )}
    </div>
  );
}
