import type { Layout } from "@erp/documents";
import { Dialog } from "@erp/ui-web";
import { useEffect, useState } from "react";

import { useI18n } from "../../../providers/I18nProvider";
import { usePreview, useStudents } from "../queries";
import { pageSizeMm } from "../types";
import { MM_TO_PX } from "./ElementView";

type PreviewMode = "sample" | "student";

export function PreviewDialog({
  open,
  layout,
  onClose,
}: {
  open: boolean;
  layout: Layout;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [mode, setMode] = useState<PreviewMode>("sample");
  const [studentQuery, setStudentQuery] = useState("");
  const [studentId, setStudentId] = useState<string | null>(null);
  const students = useStudents(studentQuery, open && mode === "student");
  const preview = usePreview(layout, mode, studentId, open);

  useEffect(() => {
    if (open) return;
    setMode("sample");
    setStudentQuery("");
    setStudentId(null);
  }, [open]);

  const page = pageSizeMm(layout.page);
  const media = preview.data?.media_mm ?? [page.width, page.height];
  const frameWidth = media[0] * MM_TO_PX;
  const frameHeight = media[1] * MM_TO_PX;
  const available = typeof window === "undefined" ? 1000 : Math.min(1100, window.innerWidth - 120);
  const scale = Math.min(1, Math.max(0.2, available / frameWidth));

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("documents.editor.preview_title")}
      description={t("documents.editor.preview_hint")}
      wide
      closeLabel={t("documents.editor.close_preview")}
      footer={
        <button
          type="button"
          className="ui-btn ui-btn--outline"
          data-testid="preview-close"
          onClick={onClose}
        >
          {t("documents.editor.close_preview")}
        </button>
      }
    >
      <div className="doc-preview" data-testid="preview-dialog">
        <div className="doc-preview__controls">
          <fieldset className="doc-preview__modes">
            <legend className="ui-label">{t("documents.preview.mode")}</legend>
            <label className="doc-preview__mode">
              <input
                type="radio"
                name="preview-mode"
                value="sample"
                checked={mode === "sample"}
                onChange={() => setMode("sample")}
                data-testid="preview-mode-sample"
              />
              {t("documents.preview.sample")}
            </label>
            <label className="doc-preview__mode">
              <input
                type="radio"
                name="preview-mode"
                value="student"
                checked={mode === "student"}
                onChange={() => setMode("student")}
                data-testid="preview-mode-student"
              />
              {t("documents.preview.student")}
            </label>
          </fieldset>

          {mode === "student" ? (
            <div className="doc-preview__student">
              <div className="ui-field">
                <label className="ui-label" htmlFor="preview-student-search">
                  {t("documents.preview.student_search")}
                </label>
                <input
                  id="preview-student-search"
                  className="ui-input"
                  type="search"
                  value={studentQuery}
                  placeholder={t("documents.preview.student_search_placeholder")}
                  onChange={(event) => setStudentQuery(event.target.value)}
                  data-testid="preview-student-search"
                />
              </div>
              <div className="ui-field">
                <label className="ui-label" htmlFor="preview-student">
                  {t("documents.preview.student_select")}
                </label>
                <select
                  id="preview-student"
                  className="ui-select"
                  value={studentId ?? ""}
                  onChange={(event) => setStudentId(event.target.value || null)}
                  data-testid="preview-student"
                >
                  <option value="">{t("documents.preview.student_placeholder")}</option>
                  {(students.data?.items ?? []).map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.student_number} — {student.person.full_name}
                    </option>
                  ))}
                </select>
                {students.isSuccess && !students.data.items.length ? (
                  <p className="ui-help">{t("documents.preview.no_students")}</p>
                ) : null}
              </div>
              <p className="ui-help">{t("documents.preview.real_hint")}</p>
            </div>
          ) : null}
        </div>

        {preview.isPending ? (
          <p className="doc-copy" data-testid="preview-loading">
            {t("documents.preview.loading")}
          </p>
        ) : null}
        {preview.isError ? (
          <p role="alert" className="doc-copy" data-testid="preview-error">
            {t("documents.preview.error")}
          </p>
        ) : null}
        {preview.data ? (
          <div
            className="doc-preview__frame-wrap"
            style={{ width: frameWidth * scale, height: frameHeight * scale }}
          >
            <iframe
              className="doc-preview__frame"
              title={t("documents.preview.frame_title")}
              data-testid="preview-frame"
              srcDoc={preview.data.html}
              style={{
                width: frameWidth,
                height: frameHeight,
                transform: `scale(${scale})`,
                background: "var(--doc-paper)",
              }}
            />
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}
