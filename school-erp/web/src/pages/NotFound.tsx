import { Link } from "react-router-dom";

import { useI18n } from "../providers/I18nProvider";

export function NotFoundPage() {
  const { t } = useI18n();
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background p-4 text-center">
      <h1 className="text-2xl font-semibold">{t("common.not_found")}</h1>
      <Link className="text-sm text-primary underline" to="/">
        {t("nav.dashboard")}
      </Link>
    </main>
  );
}
