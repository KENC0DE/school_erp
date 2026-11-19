import { ApiRequestError } from "@erp/api-client";
import { useId, useState, type FormEvent } from "react";

import { api } from "../lib/api";
import { useI18n } from "../providers/I18nProvider";
import { Button } from "./ui/Button";

export interface UploadedFile {
  id: string;
  name: string;
  mime: string;
  size_bytes: number;
  checksum_sha256: string;
  url: string;
  thumbnail_url: string | null;
  has_thumbnail: boolean;
  is_private: boolean;
  owner_entity_type: string | null;
  owner_entity_id: string | null;
}

interface FileUploadProps {
  onUploaded?: (file: UploadedFile) => void;
  accept?: string;
  ownerEntityType?: string;
  ownerEntityId?: string;
  isPrivate?: boolean;
  maxBytes?: number;
}

const DEFAULT_MAX_BYTES = 25_000_000;

export function FileUpload({
  onUploaded,
  accept = ".png,.jpg,.jpeg,.webp,.pdf,.csv,.txt,.docx,.xlsx",
  ownerEntityType,
  ownerEntityId,
  isPrivate = true,
  maxBytes = DEFAULT_MAX_BYTES,
}: FileUploadProps) {
  const { t } = useI18n();
  const inputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<UploadedFile | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || busy) return;
    setError(null);
    if (file.size > maxBytes) {
      setError(t("files.error.too_large", { max: Math.round(maxBytes / 1_000_000) }));
      return;
    }
    const form = new FormData();
    form.append("file", file);
    form.append("is_private", String(isPrivate));
    if (ownerEntityType) form.append("owner_entity_type", ownerEntityType);
    if (ownerEntityId) form.append("owner_entity_id", ownerEntityId);
    setBusy(true);
    try {
      const result = await api.postForm<UploadedFile>("/api/v1/files", form);
      setUploaded(result);
      setFile(null);
      onUploaded?.(result);
    } catch (caught) {
      if (caught instanceof ApiRequestError) {
        if (caught.status === 413) setError(t("files.error.too_large", { max: Math.round(maxBytes / 1_000_000) }));
        else if (caught.status === 415) setError(t("files.error.unsupported"));
        else setError(t("files.error.failed"));
      } else {
        setError(t("files.error.failed"));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="space-y-2" onSubmit={(event) => void submit(event)}>
      <label className="block text-sm font-medium" htmlFor={inputId}>
        {t("files.choose")}
      </label>
      <input
        id={inputId}
        type="file"
        accept={accept}
        className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm file:text-foreground"
        onChange={(event) => {
          setUploaded(null);
          setError(null);
          setFile(event.target.files?.[0] ?? null);
        }}
      />
      <p className="text-xs text-muted-foreground">
        {t("files.hint", { max: Math.round(maxBytes / 1_000_000) })}
      </p>
      <Button type="submit" disabled={!file || busy}>
        {busy ? t("files.uploading") : t("files.upload")}
      </Button>
      {uploaded ? (
        <p role="status" className="text-sm text-muted-foreground">
          {t("files.uploaded", { name: uploaded.name })}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </form>
  );
}
