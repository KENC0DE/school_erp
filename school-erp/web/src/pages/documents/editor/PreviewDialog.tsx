import type { Layout } from "@erp/documents";
import { Dialog } from "@erp/ui-web";

import { useI18n } from "../../../providers/I18nProvider";
import type { FieldDefinition } from "../types";
import { pageSizeMm } from "../types";
import { ElementView, MM_TO_PX } from "./ElementView";

export function PreviewDialog({
  open,
  layout,
  fields,
  onClose,
}: {
  open: boolean;
  layout: Layout;
  fields: Map<string, FieldDefinition>;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const page = pageSizeMm(layout.page);
  const pageWidth = page.width * MM_TO_PX;
  const pageHeight = page.height * MM_TO_PX;
  const available = typeof window === "undefined" ? 1000 : Math.min(1100, window.innerWidth - 120);
  const scale = Math.min(1, Math.max(0.2, available / pageWidth));

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
        <div style={{ width: pageWidth * scale, height: pageHeight * scale }}>
          <div
            className="doc-page doc-page--preview"
            data-testid="preview-page"
            style={{
              width: pageWidth,
              height: pageHeight,
              transform: `scale(${scale})`,
              background: layout.page.background_colour ?? "var(--doc-paper)",
            }}
          >
            {[...layout.elements]
              .sort((a, b) => a.z - b.z)
              .map((element) => (
                <ElementView key={element.id} element={element} fields={fields} t={t} />
              ))}
          </div>
        </div>
      </div>
    </Dialog>
  );
}
