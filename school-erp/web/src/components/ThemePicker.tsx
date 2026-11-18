import { useI18n } from "../providers/I18nProvider";
import { useTheme } from "../providers/ThemeProvider";

export function ThemePicker() {
  const { t } = useI18n();
  const { themeKey, available, setThemeKey } = useTheme();

  if (available.length === 0) return null;

  return (
    <select
      aria-label={t("themes.choice")}
      value={themeKey ?? ""}
      onChange={(event) => void setThemeKey(event.target.value || null)}
      className="ui-select"
    >
      <option value="">{t("themes.school_default")}</option>
      {available.map((theme) => (
        <option key={theme.key} value={theme.key}>
          {theme.name}
        </option>
      ))}
    </select>
  );
}
