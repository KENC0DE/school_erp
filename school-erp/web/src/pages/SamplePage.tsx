import { ApiRequestError } from "@erp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { EmptyState, ErrorState, LoadingState } from "@erp/ui-web";

import { Button } from "../components/ui/Button";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { api } from "../lib/api";
import { requestIdOf } from "../lib/errors";
import { useI18n } from "../providers/I18nProvider";

interface Note {
  id: string;
  content: string;
  author_name: string;
  created_at: string | null;
}

interface NoteList {
  items: Note[];
  next_cursor: string | null;
}

export function SamplePage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");

  const notes = useQuery({
    queryKey: ["sample", "notes"],
    queryFn: () => api.get<NoteList>("/api/v1/sample/notes"),
    retry: false,
  });

  const create = useMutation({
    mutationFn: (text: string) => api.post<Note>("/api/v1/sample/notes", { content: text }),
    onSuccess: () => {
      setContent("");
      void queryClient.invalidateQueries({ queryKey: ["sample", "notes"] });
    },
  });

  const disabled =
    notes.error instanceof ApiRequestError && notes.error.code === "MODULE_DISABLED";

  function submit(event: FormEvent) {
    event.preventDefault();
    if (content.trim()) create.mutate(content.trim());
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">{t("sample.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("sample.intro")}</p>
      </div>

      {disabled ? (
        <Card>
          <CardContent className="pt-5 text-sm text-muted-foreground">{t("sample.disabled")}</CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{t("sample.notes")}</CardTitle>
              <CardDescription>{t("sample.intro")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <form className="flex gap-2" onSubmit={submit}>
                <label className="sr-only" htmlFor="note-content">
                  {t("sample.note_placeholder")}
                </label>
                <Input
                  id="note-content"
                  value={content}
                  maxLength={2000}
                  placeholder={t("sample.note_placeholder")}
                  onChange={(event) => setContent(event.target.value)}
                />
                <Button type="submit" disabled={create.isPending}>
                  {t("sample.add_note")}
                </Button>
              </form>
              {notes.isLoading ? (
                <LoadingState label={t("common.loading")} rows={2} columns={2} />
              ) : notes.isError && !disabled ? (
                <ErrorState
                  title={t("common.error")}
                  requestId={requestIdOf(notes.error)}
                  requestIdLabel={t("common.request_id")}
                  retry={
                    <Button size="sm" variant="outline" onClick={() => void notes.refetch()}>
                      {t("common.retry")}
                    </Button>
                  }
                />
              ) : (notes.data?.items ?? []).length === 0 ? (
                <EmptyState title={t("sample.empty")} />
              ) : (
                <ul className="divide-y divide-border">
                  {(notes.data?.items ?? []).map((note) => (
                    <li key={note.id} className="flex items-start justify-between gap-3 py-2">
                      <span className="text-sm">{note.content}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">{note.author_name}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
          {create.isSuccess ? <p className="text-sm text-primary">{t("sample.created")}</p> : null}
          {create.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {create.error instanceof ApiRequestError ? create.error.message : t("common.error")}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
