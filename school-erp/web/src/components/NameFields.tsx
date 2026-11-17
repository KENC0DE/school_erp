import { Input } from "./ui/Input";
import { useI18n } from "../providers/I18nProvider";

export interface NameValue {
  given_name_en: string;
  father_name_en: string;
  grandfather_name_en: string;
  given_name_am: string;
  father_name_am: string;
  grandfather_name_am: string;
}

export const EMPTY_NAME: NameValue = {
  given_name_en: "",
  father_name_en: "",
  grandfather_name_en: "",
  given_name_am: "",
  father_name_am: "",
  grandfather_name_am: "",
};

type Part = "given" | "father" | "grandfather";

/**
 * Three-part name inputs in both scripts. There is deliberately no "last name":
 * Ethiopian names are given name, father's name, grandfather's name (ARCH §5.8).
 */
export function NameFields({
  value,
  onChange,
  disabled = false,
}: {
  value: NameValue;
  onChange: (value: NameValue) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();

  const set = (field: keyof NameValue) => (next: string) => onChange({ ...value, [field]: next });

  const group = (script: "en" | "am") => (
    <div className="grid gap-3 md:grid-cols-3">
      {(["given", "father", "grandfather"] as Part[]).map((part) => {
        const field = `${part}_name_${script}` as keyof NameValue;
        const label = t(`name.${part}${script === "am" ? ".am" : ""}`);
        return (
          <label key={field} className="space-y-1 text-sm">
            <span className="text-muted-foreground">{label}</span>
            <Input
              data-testid={`name-${field}`}
              value={value[field]}
              disabled={disabled}
              lang={script === "am" ? "am" : "en"}
              dir="auto"
              onChange={(event) => set(field)(event.target.value)}
            />
          </label>
        );
      })}
    </div>
  );

  return (
    <fieldset className="space-y-4" data-testid="name-fields">
      <legend className="text-sm font-semibold">{t("name.title")}</legend>
      <p className="text-xs text-muted-foreground">{t("name.hint")}</p>
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t("name.latin")}
        </p>
        {group("en")}
      </div>
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t("name.amharic")}
        </p>
        {group("am")}
      </div>
      <p className="text-xs text-muted-foreground">{t("name.no_last_name")}</p>
    </fieldset>
  );
}
