import { ApiRequestError } from "@erp/api-client";
import { useQueryClient } from "@tanstack/react-query";
import { useState, type ChangeEvent } from "react";

import { api } from "../../lib/api";
import { useI18n } from "../../providers/I18nProvider";
import { STUDENTS, useStudentPhoto } from "./queries";
import type { StudentDetail, UploadedPhoto } from "./types";

export function StudentPhotoCard({
  student,
  canManage,
}: {
  student: StudentDetail;
  canManage: boolean;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const hasPhoto = Boolean(student.person.photo_file_id);
  const photo = useStudentPhoto(student.id, hasPhoto);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function replace(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const uploaded = await api.postForm<UploadedPhoto>(
        `${STUDENTS}/photos?person_id=${encodeURIComponent(student.person.id)}`,
        form,
      );
      await api.patch(`${STUDENTS}/${student.id}`, {
        person: { photo_file_id: uploaded.id },
        row_version: student.row_version,
      });
      await queryClient.invalidateQueries({ queryKey: ["students", "detail", student.id] });
      await queryClient.invalidateQueries({ queryKey: ["students", "photo", student.id] });
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("students.photo.failed"));
    } finally {
      setBusy(false);
    }
  }

  const initials = [student.person.given_name_en, student.person.father_name_en]
    .filter(Boolean)
    .map((part) => part!.charAt(0).toUpperCase())
    .join("");

  return (
    <div className="flex flex-col items-center gap-2" data-testid="student-photo">
      {photo.data ? (
        <img
          src={photo.data.thumbnail_url ?? photo.data.url}
          alt={student.person.full_name}
          className="h-28 w-28 rounded-full border border-border object-cover"
        />
      ) : (
        <span
          aria-hidden="true"
          className="flex h-28 w-28 items-center justify-center rounded-full bg-muted text-2xl font-semibold text-muted-foreground"
        >
          {initials}
        </span>
      )}
      {canManage ? (
        <label className="cursor-pointer text-sm">
          <span className="ui-link">{t("students.photo.replace")}</span>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="ui-visually-hidden"
            disabled={busy}
            onChange={(event) => void replace(event)}
          />
        </label>
      ) : null}
      {busy ? <p className="text-xs text-muted-foreground">{t("students.photo.uploading")}</p> : null}
      {error ? (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
