import { ApiRequestError } from "@erp/api-client";
import { formatDual } from "@erp/calendar";
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Page,
  PageHeader,
  Select,
} from "@erp/ui-web";
import { useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../../lib/api";
import { requestIdOf } from "../../lib/errors";
import { useAuth } from "../../providers/AuthProvider";
import { useI18n } from "../../providers/I18nProvider";
import { GenerationDialog } from "./GenerationDialog";
import { useStarters, useTemplates } from "./queries";
import {
  DOC_TYPES,
  isDraft,
  type DocType,
  type TemplateDetail,
  type TemplateFile,
  type TemplateSummary,
} from "./types";

function TemplateCard({
  template,
  onGenerate,
  onDuplicate,
  onDelete,
  onExport,
}: {
  template: TemplateSummary;
  onGenerate: (template: TemplateSummary) => void;
  onDuplicate: (template: TemplateSummary) => void;
  onDelete: (template: TemplateSummary) => void;
  onExport: (template: TemplateSummary) => void;
}) {
  const { t, locale } = useI18n();
  return (
    <article className="doc-card" data-testid={`template-${template.key}`}>
      <div className="doc-card__top">
        <Badge>{t(`documents.type.${template.doc_type}`)}</Badge>
        <span className="doc-card__versions">
          {t("documents.list.versions", { count: template.version_count })}
        </span>
      </div>
      <h2 className="doc-card__title">
        <Link to={`/documents/${template.id}`} data-testid={`template-open-${template.key}`}>
          {template.name}
        </Link>
      </h2>
      {template.description ? <p className="doc-card__description">{template.description}</p> : null}
      <div className="doc-card__states">
        {isDraft(template) ? (
          <Badge variant="warning">
            {t("documents.list.draft", { number: template.draft_version_number ?? 1 })}
          </Badge>
        ) : template.current_version_id ? (
          <Badge variant="success">
            {t("documents.list.published", { number: template.current_version_number ?? 1 })}
          </Badge>
        ) : null}
        <span className="ui-num doc-card__updated">
          {formatDual(new Date(template.updated_at), "both", locale === "am" ? "am" : "en")}
        </span>
      </div>
      <div className="doc-card__actions">
        <Link className="ui-btn ui-btn--primary ui-btn--sm" to={`/documents/${template.id}`}>
          {t("documents.list.open")}
        </Link>
        {template.current_version_id ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onGenerate(template)}
            data-testid={`template-generate-${template.key}`}
          >
            {t("documents.list.generate")}
          </Button>
        ) : null}
        <Button variant="outline" size="sm" onClick={() => onDuplicate(template)}>
          {t("documents.list.duplicate")}
        </Button>
        <Button variant="outline" size="sm" onClick={() => onExport(template)}>
          {t("documents.list.export")}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDelete(template)}>
          {t("documents.list.delete")}
        </Button>
      </div>
    </article>
  );
}

export function DocumentsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const [docType, setDocType] = useState<DocType | "">("");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const templates = useTemplates(docType || null, deferredSearch);

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [newType, setNewType] = useState<DocType>("certificate_completion");
  const [starter, setStarter] = useState("blank");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const starters = useStarters(creating);

  const [duplicating, setDuplicating] = useState<TemplateSummary | null>(null);
  const [duplicateName, setDuplicateName] = useState("");
  const [deleting, setDeleting] = useState<TemplateSummary | null>(null);
  const [generating, setGenerating] = useState<TemplateSummary | null>(null);

  const canDesign =
    (user?.permissions ?? []).includes("*") ||
    (user?.permissions ?? []).includes("documents.template.design");

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["documents"] });

  const openCreate = () => {
    setCreating(true);
    setName("");
    setStarter("blank");
    setNewType("certificate_completion");
    setError(null);
    setNotice(null);
  };

  const chooseStarter = (key: string) => {
    setStarter(key);
    const entry = starters.data?.items.find((item) => item.key === key);
    if (entry) setNewType(entry.doc_type);
  };

  const create = async () => {
    if (!name.trim()) {
      setError(t("documents.new.name_required"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<TemplateDetail>("/api/v1/documents/templates", {
        name: name.trim(),
        doc_type: starter === "blank" ? newType : undefined,
        starter: starter === "blank" ? null : starter,
      });
      setCreating(false);
      refresh();
      navigate(`/documents/${created.id}`);
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const duplicate = async () => {
    if (!duplicating || !duplicateName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<TemplateDetail>(
        `/api/v1/documents/templates/${duplicating.id}/duplicate`,
        { name: duplicateName.trim() },
      );
      setDuplicating(null);
      setNotice(t("documents.list.duplicated"));
      refresh();
      navigate(`/documents/${created.id}`);
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!deleting) return;
    setBusy(true);
    try {
      await api.del(`/api/v1/documents/templates/${deleting.id}`);
      setDeleting(null);
      setNotice(t("documents.list.deleted"));
      refresh();
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const exportTemplate = async (template: TemplateSummary) => {
    try {
      const payload = await api.get<TemplateFile>(
        `/api/v1/documents/templates/${template.id}/export`,
      );
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${template.key}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setError(t("common.error"));
    }
  };

  const importTemplate = async (file: File) => {
    setError(null);
    try {
      const payload = JSON.parse(await file.text()) as TemplateFile;
      const created = await api.post<TemplateDetail>("/api/v1/documents/templates/import", payload);
      setNotice(t("documents.list.imported"));
      refresh();
      navigate(`/documents/${created.id}`);
    } catch (caught) {
      setError(caught instanceof ApiRequestError ? caught.message : t("documents.list.import_failed"));
    }
  };

  if (!canDesign) {
    return (
      <Page>
        <PageHeader title={t("documents.list.title")} description={t("documents.list.intro")} />
        <p role="alert" className="text-sm text-destructive" data-testid="documents-permission">
          {t("error.permission_denied")}
        </p>
      </Page>
    );
  }

  return (
    <Page>
      <div className="space-y-5" data-testid="documents-page">
        <PageHeader
          title={t("documents.list.title")}
          description={t("documents.list.intro")}
          actions={
            <>
              <input
                ref={fileInput}
                type="file"
                accept="application/json,.json"
                aria-label={t("documents.list.import")}
                className="ui-visually-hidden"
                data-testid="template-import-input"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void importTemplate(file);
                  event.target.value = "";
                }}
              />
              <Button variant="outline" onClick={() => fileInput.current?.click()}>
                {t("documents.list.import")}
              </Button>
              <Link className="ui-btn ui-btn--outline ui-btn--sm" to="/documents/issued">
                {t("documents.list.issued")}
              </Link>
              <Button onClick={openCreate} data-testid="template-new">
                {t("documents.list.new")}
              </Button>
            </>
          }
        />

        {notice ? (
          <p role="status" className="text-sm text-muted-foreground" data-testid="documents-notice">
            {notice}
          </p>
        ) : null}
        {error && !creating && !duplicating ? (
          <p role="alert" className="text-sm text-destructive" data-testid="documents-error">
            {error}
          </p>
        ) : null}

        <div className="ui-table-toolbar doc-filters">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("documents.list.search")}
            aria-label={t("documents.list.search")}
            data-testid="template-search"
          />
          <Select
            value={docType}
            aria-label={t("documents.list.filter_type")}
            data-testid="template-type-filter"
            onChange={(event) => setDocType(event.target.value as DocType | "")}
          >
            <option value="">{t("documents.list.all_types")}</option>
            {DOC_TYPES.map((value) => (
              <option key={value} value={value}>
                {t(`documents.type.${value}`)}
              </option>
            ))}
          </Select>
        </div>

        {templates.isPending ? (
          <LoadingState label={t("documents.list.loading")} testId="documents-loading" />
        ) : templates.isError ? (
          <ErrorState
            title={t("documents.list.error")}
            requestId={requestIdOf(templates.error)}
            retry={
              <Button variant="outline" onClick={() => void templates.refetch()}>
                {t("documents.list.retry")}
              </Button>
            }
          />
        ) : (templates.data?.items.length ?? 0) === 0 ? (
          <EmptyState
            title={t("documents.list.empty_title")}
            description={t("documents.list.empty_description")}
            action={<Button onClick={openCreate}>{t("documents.list.new")}</Button>}
            testId="documents-empty"
          />
        ) : (
          <div className="doc-card-grid" data-testid="template-list">
            {templates.data?.items.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                onGenerate={setGenerating}
                onDuplicate={(value) => {
                  setDuplicating(value);
                  setDuplicateName(`${value.name} copy`);
                }}
                onDelete={setDeleting}
                onExport={(value) => void exportTemplate(value)}
              />
            ))}
          </div>
        )}
      </div>

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title={t("documents.new.title")}
        description={t("documents.new.description")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="outline" onClick={() => setCreating(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => void create()} disabled={busy} data-testid="template-create">
              {busy ? t("documents.new.creating") : t("documents.new.create")}
            </Button>
          </>
        }
      >
        <div className="ui-field">
          <Field label={t("documents.new.name")} required>
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("documents.new.name_placeholder")}
              data-testid="template-name"
              autoFocus
            />
          </Field>
          <Field label={t("documents.new.starter")} hint={t("documents.new.starter_hint")}>
            <Select
              value={starter}
              data-testid="template-starter"
              onChange={(event) => chooseStarter(event.target.value)}
            >
              <option value="blank">{t("documents.new.blank")}</option>
              {(starters.data?.items ?? []).map((item) => (
                <option key={item.key} value={item.key}>
                  {t(item.name_key)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("documents.new.doc_type")}>
            <Select
              value={newType}
              disabled={starter !== "blank"}
              data-testid="template-doc-type"
              onChange={(event) => setNewType(event.target.value as DocType)}
            >
              {DOC_TYPES.map((value) => (
                <option key={value} value={value}>
                  {t(`documents.type.${value}`)}
                </option>
              ))}
            </Select>
          </Field>
          {starters.isPending ? <p className="ui-help">{t("documents.new.loading_starters")}</p> : null}
          {error ? (
            <p role="alert" className="ui-error-text" data-testid="template-create-error">
              {error}
            </p>
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={Boolean(duplicating)}
        onClose={() => setDuplicating(null)}
        title={t("documents.list.duplicate")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="outline" onClick={() => setDuplicating(null)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => void duplicate()} disabled={busy} data-testid="template-duplicate">
              {t("documents.list.duplicate")}
            </Button>
          </>
        }
      >
        <Field label={t("documents.new.name")} required>
          <Input value={duplicateName} onChange={(event) => setDuplicateName(event.target.value)} autoFocus />
        </Field>
        {error ? <p role="alert" className="ui-error-text">{error}</p> : null}
      </Dialog>

      <Dialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title={t("documents.list.delete_title")}
        description={t("documents.list.delete_body")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button variant="outline" onClick={() => setDeleting(null)}>
              {t("common.cancel")}
            </Button>
            <Button variant="destructive" onClick={() => void remove()} disabled={busy} data-testid="template-delete-confirm">
              {t("documents.list.delete_confirm")}
            </Button>
          </>
        }
      >
        <p className="doc-copy">{deleting?.name}</p>
      </Dialog>

      <GenerationDialog
        open={Boolean(generating)}
        onClose={() => setGenerating(null)}
        templates={templates.data?.items ?? []}
        initialTemplateId={generating?.id}
      />
    </Page>
  );
}
