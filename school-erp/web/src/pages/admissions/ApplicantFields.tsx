import { Field, Input, Select } from "@erp/ui-web";

import { EMPTY_NAME, NameFields, type NameValue } from "../../components/NameFields";
import { useI18n } from "../../providers/I18nProvider";

export interface ApplicantDraft {
  names: NameValue;
  sex: string;
  dateOfBirth: string;
  placeOfBirth: string;
  nationality: string;
  phone: string;
  email: string;
  address: string;
}

export const EMPTY_APPLICANT: ApplicantDraft = {
  names: { ...EMPTY_NAME },
  sex: "",
  dateOfBirth: "",
  placeOfBirth: "",
  nationality: "",
  phone: "",
  email: "",
  address: "",
};

export function ApplicantFields({
  value,
  onChange,
  disabled = false,
}: {
  value: ApplicantDraft;
  onChange: (value: ApplicantDraft) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const set = <Key extends keyof ApplicantDraft>(key: Key, next: ApplicantDraft[Key]) =>
    onChange({ ...value, [key]: next });

  return (
    <div className="space-y-4">
      <NameFields
        value={value.names}
        onChange={(names) => set("names", names)}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("students.sex")}>
          <Select
            value={value.sex}
            disabled={disabled}
            onChange={(event) => set("sex", event.target.value)}
          >
            <option value="">{t("students.sex.unspecified")}</option>
            <option value="male">{t("students.sex.male")}</option>
            <option value="female">{t("students.sex.female")}</option>
          </Select>
        </Field>
        <Field label={t("students.date_of_birth")}>
          <Input
            type="date"
            value={value.dateOfBirth}
            disabled={disabled}
            onChange={(event) => set("dateOfBirth", event.target.value)}
          />
        </Field>
        <Field label={t("students.place_of_birth")}>
          <Input
            value={value.placeOfBirth}
            disabled={disabled}
            onChange={(event) => set("placeOfBirth", event.target.value)}
          />
        </Field>
        <Field label={t("students.nationality")}>
          <Input
            value={value.nationality}
            disabled={disabled}
            onChange={(event) => set("nationality", event.target.value)}
          />
        </Field>
        <Field label={t("students.phone")}>
          <Input
            value={value.phone}
            disabled={disabled}
            onChange={(event) => set("phone", event.target.value)}
          />
        </Field>
        <Field label={t("students.email")}>
          <Input
            type="email"
            value={value.email}
            disabled={disabled}
            onChange={(event) => set("email", event.target.value)}
          />
        </Field>
      </div>
      <Field label={t("students.address")}>
        <Input
          value={value.address}
          disabled={disabled}
          onChange={(event) => set("address", event.target.value)}
        />
      </Field>
    </div>
  );
}
