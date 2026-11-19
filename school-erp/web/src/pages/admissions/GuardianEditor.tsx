import { Button, Field, Input, Select } from "@erp/ui-web";

import { EMPTY_NAME, NameFields } from "../../components/NameFields";
import { useI18n } from "../../providers/I18nProvider";
import type { GuardianDraft } from "./types";

const RELATIONSHIPS = ["mother", "father", "guardian", "grandparent", "sibling", "other"] as const;

let sequence = 0;

export function newGuardian(overrides: Partial<GuardianDraft> = {}): GuardianDraft {
  sequence += 1;
  return {
    uid: `guardian-${sequence}`,
    relationship: "mother",
    is_primary: false,
    can_pickup: true,
    wants_account: false,
    names: { ...EMPTY_NAME },
    phone: "",
    email: "",
    ...overrides,
  };
}

export function GuardianEditor({
  guardians,
  onChange,
  requireGuardian,
  showAccountOption = false,
}: {
  guardians: GuardianDraft[];
  onChange: (guardians: GuardianDraft[]) => void;
  requireGuardian: boolean;
  showAccountOption?: boolean;
}) {
  const { t } = useI18n();

  const update = (index: number, patch: Partial<GuardianDraft>) => {
    onChange(guardians.map((guardian, position) => (position === index ? { ...guardian, ...patch } : guardian)));
  };

  const setPrimary = (index: number) => {
    onChange(
      guardians.map((guardian, position) => ({
        ...guardian,
        is_primary: position === index,
      })),
    );
  };

  return (
    <fieldset className="space-y-3" data-testid="admission-guardians">
      <legend className="text-sm font-semibold">{t("admissions.guardians")}</legend>
      {requireGuardian ? (
        <p className="text-xs text-muted-foreground">{t("admissions.form.require_guardian")}</p>
      ) : null}
      {guardians.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("admissions.guardian.empty")}</p>
      ) : null}
      {guardians.map((guardian, index) => (
        <div key={guardian.uid} className="space-y-3 rounded-md border border-border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium">
              {t("admissions.guardian")} {index + 1}
            </p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onChange(guardians.filter((_, position) => position !== index))}
            >
              {t("admissions.guardian.remove")}
            </Button>
          </div>
          <NameFields
            value={guardian.names}
            onChange={(names) => update(index, { names })}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("admissions.guardian.relationship")}>
              <Select
                value={guardian.relationship}
                onChange={(event) => update(index, { relationship: event.target.value })}
              >
                {RELATIONSHIPS.map((relationship) => (
                  <option key={relationship} value={relationship}>
                    {t(`admissions.relationship.${relationship}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("students.phone")}>
              <Input
                value={guardian.phone}
                onChange={(event) => update(index, { phone: event.target.value })}
              />
            </Field>
            <Field label={t("students.email")}>
              <Input
                type="email"
                value={guardian.email}
                onChange={(event) => update(index, { email: event.target.value })}
              />
            </Field>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={guardian.is_primary}
                onChange={() => setPrimary(index)}
              />
              {t("admissions.guardian.primary")}
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={guardian.can_pickup}
                onChange={(event) => update(index, { can_pickup: event.target.checked })}
              />
              {t("admissions.guardian.can_pickup")}
            </label>
            {showAccountOption ? (
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-input"
                  checked={guardian.wants_account}
                  onChange={(event) => update(index, { wants_account: event.target.checked })}
                />
                {t("admissions.guardian.wants_account")}
              </label>
            ) : null}
          </div>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        onClick={() =>
          onChange([
            ...guardians,
            newGuardian({ is_primary: guardians.length === 0 }),
          ])
        }
      >
        {t("admissions.guardian.add")}
      </Button>
    </fieldset>
  );
}
