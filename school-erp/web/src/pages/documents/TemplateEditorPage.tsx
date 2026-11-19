import { ApiRequestError } from "@erp/api-client";
import type { Layout, LayoutElement } from "@erp/documents";
import {
  Badge,
  Button,
  Checkbox,
  Dialog,
  ErrorState,
  LoadingState,
  Page,
  PageHeader,
} from "@erp/ui-web";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { CanvasStage } from "./editor/CanvasStage";
import {
  PLACEHOLDER_SOURCES,
  insertToken,
  newBarcode,
  newFieldText,
  newImage,
  newQr,
  newShape,
  newTable,
  newText,
  tokenFor,
} from "./editor/elements";
import { FieldPalette } from "./editor/FieldPalette";
import { patchElement, useLayoutHistory, type LayoutHistory } from "./editor/history";
import { Inspector } from "./editor/Inspector";
import { LayersPanel } from "./editor/LayersPanel";
import { PageSetupPanel } from "./editor/PageSetupPanel";
import { PreviewDialog } from "./editor/PreviewDialog";
import { useFields, useTemplate, useVersion } from "./queries";
import type { FieldDefinition, TemplateDetail, VersionDetail } from "./types";

function addElement(
  history: LayoutHistory,
  create: (layout: Layout) => LayoutElement,
  select: (id: string) => void,
) {
  const element = create(history.layout);
  history.commit({ ...history.layout, elements: [...history.layout.elements, element] });
  select(element.id);
}

function Editor({
  detail,
  version,
  fields,
  fieldsByKey,
  notice,
  setNotice,
  refresh,
}: {
  detail: TemplateDetail;
  version: VersionDetail;
  fields: FieldDefinition[];
  fieldsByKey: Map<string, FieldDefinition>;
  notice: string | null;
  setNotice: (value: string | null) => void;
  refresh: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const history = useLayoutHistory(version.layout);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(() => {
    if (typeof window === "undefined") return 0.8;
    return window.innerWidth < 640 ? 0.38 : window.innerWidth < 1024 ? 0.6 : 0.85;
  });
  const [snap, setSnap] = useState(true);
  const [preview, setPreview] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const rowVersion = useRef(version.row_version);
  const readOnly = version.status !== "draft";
  const selected = history.layout.elements.find((element) => element.id === selectedId) ?? null;

  const save = async () => {
    if (readOnly || saving) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.patch<VersionDetail>(
        `/api/v1/documents/templates/${detail.id}/versions/${version.id}`,
        { layout: history.layout, row_version: rowVersion.current },
      );
      rowVersion.current = saved.row_version;
      queryClient.setQueryData(["documents", "version", detail.id, version.id], saved);
      history.markSaved(saved.layout);
      setNotice(t("documents.editor.saved_toast"));
      refresh();
    } catch (caught) {
      setError(
        caught instanceof ApiRequestError && caught.status === 409
          ? t("documents.editor.save_conflict")
          : caught instanceof ApiRequestError
            ? caught.message
            : t("common.error"),
      );
    } finally {
      setSaving(false);
    }
  };

  const publish = async () => {
    setPublishing(true);
    setError(null);
    try {
      await api.post(
        `/api/v1/documents/templates/${detail.id}/versions/${version.id}/publish`,
      );
      setPublishOpen(false);
      setNotice(t("documents.editor.published_toast", { number: version.version_number }));
      refresh();
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("common.error"));
    } finally {
      setPublishing(false);
    }
  };

  const startDraft = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/documents/templates/${detail.id}/versions`, {});
      setNotice(t("documents.editor.start_draft"));
      refresh();
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("common.error"));
    }
  };

  useEffect(() => {
    if (!history.dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [history.dirty]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }
      const meta = event.metaKey || event.ctrlKey;
      if (meta && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) history.redo();
        else history.undo();
        return;
      }
      if (meta && event.key.toLowerCase() === "y") {
        event.preventDefault();
        history.redo();
        return;
      }
      if (meta && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void save();
        return;
      }
      if (event.key === "Escape") {
        setSelectedId(null);
        setPreview(false);
        return;
      }
      if ((event.key === "Delete" || event.key === "Backspace") && selectedId && !readOnly) {
        event.preventDefault();
        history.commit({
          ...history.layout,
          elements: history.layout.elements.filter((item) => item.id !== selectedId),
        });
        setSelectedId(null);
        return;
      }
      if (event.key.startsWith("Arrow") && selectedId && !readOnly) {
        const amount = event.shiftKey ? 10 : 1;
        const delta =
          event.key === "ArrowLeft"
            ? { x_mm: -amount }
            : event.key === "ArrowRight"
              ? { x_mm: amount }
              : event.key === "ArrowUp"
                ? { y_mm: -amount }
                : { y_mm: amount };
        event.preventDefault();
        history.commit({
          ...history.layout,
          elements: history.layout.elements.map((item) =>
            item.id === selectedId
              ? { ...item, rect: { ...item.rect, ...delta } }
              : item,
          ),
        });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const pickField = (field: FieldDefinition) => {
    if (readOnly) return;
    if (selected?.type === "text") {
      history.commit(
        patchElement(history.layout, selected.id, {
          content: insertToken(selected.content, tokenFor(field)),
        } as Partial<LayoutElement>),
      );
      return;
    }
    if (selected?.type === "table" && field.kind === "table") {
      history.commit(
        patchElement(history.layout, selected.id, {
          table: { ...selected.table, source: field.key },
        } as Partial<LayoutElement>),
      );
      return;
    }
    addElement(history, (layout) => newFieldText(layout, field.key), setSelectedId);
  };

  const add = (kind: string) => {
    if (readOnly) return;
    const create = (layout: Layout): LayoutElement => {
      switch (kind) {
        case "text":
          return newText(layout, "New text");
        case "image":
          return newImage(layout);
        case "shape":
          return newShape(layout, "rect");
        case "line":
          return newShape(layout, "line");
        case "table":
          return newTable(layout);
        case "qr":
          return newQr(layout);
        case "barcode":
          return newBarcode(layout);
        case "logo":
        case "signature":
        case "stamp":
        case "photo":
          return newImage(layout, PLACEHOLDER_SOURCES[kind]);
        default:
          return newText(layout);
      }
    };
    addElement(history, create, setSelectedId);
  };

  const fit = () => {
    const pageWidthMm = history.layout.page.size === "custom" ? history.layout.page.width_mm ?? 210 : 210;
    const available = typeof window === "undefined" ? 900 : Math.min(1100, window.innerWidth - 520);
    setZoom(Math.max(0.2, Math.min(1.4, available / (pageWidthMm * (96 / 25.4)))));
  };

  return (
    <div className="doc-editor" data-testid="template-editor">
      <aside className="doc-editor__side doc-editor__side--left">
        <FieldPalette fields={fields} onPick={pickField} />
        <LayersPanel
          layout={history.layout}
          selectedId={selectedId}
          fields={fieldsByKey}
          readOnly={readOnly}
          onSelect={setSelectedId}
          onChange={history.commit}
        />
      </aside>

      <section className="doc-editor__main">
        <div className="doc-toolbar" role="toolbar" aria-label={t("documents.editor.title")}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => (history.dirty ? setLeaving(true) : navigate("/documents"))}
            data-testid="editor-back"
          >
            ← {t("documents.editor.back")}
          </Button>
          <span className="doc-toolbar__title">{detail.name}</span>
          {readOnly ? (
            <Badge variant="success">
              {t("documents.list.published", { number: version.version_number })}
            </Badge>
          ) : (
            <Badge variant="warning">
              {t("documents.list.draft", { number: version.version_number })}
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={!history.canUndo}
            onClick={history.undo}
            aria-label={t("documents.editor.undo")}
            data-testid="editor-undo"
          >
            ↶
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!history.canRedo}
            onClick={history.redo}
            aria-label={t("documents.editor.redo")}
            data-testid="editor-redo"
          >
            ↷
          </Button>
          <span className="doc-zoom">
            <Button variant="ghost" size="sm" aria-label={t("documents.editor.zoom_out")} onClick={() => setZoom((value) => Math.max(0.2, value - 0.1))}>
              −
            </Button>
            <span className="ui-num" data-testid="editor-zoom">{Math.round(zoom * 100)}%</span>
            <Button variant="ghost" size="sm" aria-label={t("documents.editor.zoom_in")} onClick={() => setZoom((value) => Math.min(2, value + 0.1))}>
              +
            </Button>
            <Button variant="ghost" size="sm" onClick={fit}>
              {t("documents.editor.zoom_fit")}
            </Button>
          </span>
          <Checkbox
            label={t("documents.editor.grid")}
            checked={snap}
            onChange={(event) => setSnap(event.target.checked)}
          />
          <span className="doc-toolbar__spacer" />
          <span className={`doc-save-state${history.dirty ? " doc-save-state--dirty" : ""}`} data-testid="editor-save-state">
            {history.dirty ? t("documents.editor.unsaved") : t("documents.editor.saved")}
          </span>
          <Button variant="outline" size="sm" onClick={() => setPreview(true)} data-testid="editor-preview">
            {t("documents.editor.preview")}
          </Button>
          {readOnly ? (
            <Button size="sm" onClick={() => void startDraft()} data-testid="editor-start-draft">
              {t("documents.editor.start_draft")}
            </Button>
          ) : (
            <>
              <Button
                size="sm"
                onClick={() => void save()}
                disabled={!history.dirty || saving}
                data-testid="editor-save"
              >
                {saving ? t("documents.editor.saving") : t("documents.editor.save")}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setPublishOpen(true)} data-testid="editor-publish-open">
                {t("documents.editor.publish")}
              </Button>
            </>
          )}
        </div>

        {notice ? (
          <p role="status" className="doc-notice" data-testid="editor-notice">{notice}</p>
        ) : null}
        {error ? (
          <p role="alert" className="doc-notice doc-notice--error" data-testid="editor-error">{error}</p>
        ) : null}
        {readOnly ? (
          <p className="ui-help" data-testid="editor-read-only">{t("documents.editor.start_draft_hint")}</p>
        ) : null}

        <div className="doc-addbar" role="toolbar" aria-label={t("documents.editor.add")}>
          {[
            "text",
            "image",
            "shape",
            "line",
            "table",
            "qr",
            "barcode",
            "logo",
            "signature",
            "stamp",
            "photo",
          ].map((kind) => (
            <Button
              key={kind}
              variant="outline"
              size="sm"
              disabled={readOnly}
              data-testid={`add-${kind}`}
              onClick={() => add(kind)}
            >
              {t(`documents.editor.add_${kind}`)}
            </Button>
          ))}
        </div>

        <CanvasStage
          layout={history.layout}
          selectedId={selectedId}
          fields={fieldsByKey}
          t={t}
          zoom={zoom}
          snap={snap}
          readOnly={readOnly}
          onSelect={setSelectedId}
          onBeginGesture={history.beginGesture}
          onChange={history.updateLive}
        />
      </section>

      <aside className="doc-editor__side doc-editor__side--right">
        <Inspector layout={history.layout} element={selected} onChange={history.commit} />
        <PageSetupPanel layout={history.layout} readOnly={readOnly} onChange={history.commit} />
      </aside>

      <PreviewDialog
        open={preview}
        layout={history.layout}
        fields={fieldsByKey}
        onClose={() => setPreview(false)}
      />

      <Dialog
        open={leaving}
        onClose={() => setLeaving(false)}
        title={t("documents.editor.back")}
        description={t("documents.editor.unsaved_warning")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="outline" onClick={() => setLeaving(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => navigate("/documents")}>{t("documents.editor.back")}</Button>
          </>
        }
      >
        <p className="doc-copy">{t("documents.editor.unsaved")}</p>
      </Dialog>

      <Dialog
        open={publishOpen}
        onClose={() => setPublishOpen(false)}
        title={t("documents.editor.publish_confirm_title")}
        description={t("documents.editor.publish_confirm_body")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="outline" onClick={() => setPublishOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => void publish()} disabled={publishing} data-testid="editor-publish">
              {publishing ? t("documents.editor.publishing") : t("documents.editor.publish_confirm")}
            </Button>
          </>
        }
      >
        <p className="doc-copy">
          {t("documents.list.draft", { number: version.version_number })} · {detail.key}
        </p>
      </Dialog>
    </div>
  );
}

export function TemplateEditorPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { templateId } = useParams();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const detail = useTemplate(templateId ?? null);
  const versionId = detail.data?.draft_version_id ?? detail.data?.current_version_id ?? null;
  const version = useVersion(templateId ?? null, versionId);
  const fieldsQuery = useFields();
  const fields = useMemo(() => fieldsQuery.data?.items ?? [], [fieldsQuery.data]);
  const fieldsByKey = useMemo(
    () => new Map(fields.map((field) => [field.key, field])),
    [fields],
  );

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["documents", "template", templateId] });
    void queryClient.invalidateQueries({ queryKey: ["documents", "version", templateId] });
    void queryClient.invalidateQueries({ queryKey: ["documents", "templates"] });
  };

  const canDesign =
    (user?.permissions ?? []).includes("*") ||
    (user?.permissions ?? []).includes("documents.template.design");

  if (!canDesign) {
    return (
      <Page>
        <PageHeader title={t("documents.list.title")} />
        <p role="alert" className="text-sm text-destructive">{t("error.permission_denied")}</p>
      </Page>
    );
  }

  if (detail.isPending || (versionId && version.isPending)) {
    return (
      <Page>
        <LoadingState label={t("documents.editor.loading")} testId="editor-loading" />
      </Page>
    );
  }

  if (detail.isError || !detail.data || (versionId && version.isError)) {
    return (
      <Page>
        <ErrorState
          title={t("documents.editor.error")}
          requestId={requestIdOf(detail.error ?? version.error)}
          retry={
            <Button variant="outline" onClick={() => void detail.refetch()}>
              {t("documents.list.retry")}
            </Button>
          }
        />
      </Page>
    );
  }

  if (!versionId || !version.data) {
    return (
      <Page>
        <ErrorState title={t("documents.editor.error")} />
      </Page>
    );
  }

  return (
    <Page className="doc-editor-page">
      <Editor
        key={version.data.id}
        detail={detail.data}
        version={version.data}
        fields={fields}
        fieldsByKey={fieldsByKey}
        notice={notice}
        setNotice={setNotice}
        refresh={refresh}
      />
    </Page>
  );
}
