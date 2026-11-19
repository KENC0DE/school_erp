import { useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { EMPTY_NAME, NameFields, type NameValue } from "../../../src/components/NameFields";
import { useApp } from "../../../src/context/AppContext";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import {
  listLevels,
  listSections,
  listYears,
  previewRegistration,
  registerStudent,
} from "../../../src/students/api";
import { studentErrorKey } from "../../../src/students/errors";
import { hasPermission } from "../../../src/students/permissions";
import type {
  AcademicLevel,
  AcademicSection,
  AcademicYear,
  PersonInput,
  RegistrationPreview,
  StudentRegistration,
} from "../../../src/students/types";
import { useSchoolThemeContext } from "../../../src/theme/SchoolThemeContext";
import {
  Button,
  Card,
  ErrorState,
  Field,
  Muted,
  PageHeader,
  Screen,
  SectionTitle,
  SelectField,
  type SelectOption,
} from "../../../src/ui";

function clean(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function isBlank(value: string | undefined): boolean {
  return !value || !value.trim();
}

/** Mirrors the backend rule: a script is valid only when all three parts are present. */
function namesValid(names: NameValue): boolean {
  const latin = [names.given_name_en, names.father_name_en, names.grandfather_name_en];
  const amharic = [names.given_name_am, names.father_name_am, names.grandfather_name_am];
  const latinComplete = latin.every((part) => !isBlank(part));
  const amharicComplete = amharic.every((part) => !isBlank(part));
  const latinStarted = latin.some((part) => !isBlank(part));
  const amharicStarted = amharic.some((part) => !isBlank(part));
  if (latinStarted && !latinComplete) return false;
  if (amharicStarted && !amharicComplete) return false;
  return latinComplete || amharicComplete;
}

function personPayload(names: NameValue, sex: string, dateOfBirth: string): PersonInput {
  const person: PersonInput = {
    given_name_en: clean(names.given_name_en),
    father_name_en: clean(names.father_name_en),
    grandfather_name_en: clean(names.grandfather_name_en),
    given_name_am: clean(names.given_name_am),
    father_name_am: clean(names.father_name_am),
    grandfather_name_am: clean(names.grandfather_name_am),
    sex: clean(sex),
    date_of_birth: clean(dateOfBirth),
  };
  for (const key of Object.keys(person) as Array<keyof PersonInput>) {
    if (person[key] === undefined) delete person[key];
  }
  return person;
}

export default function StudentRegistrationScreen() {
  const router = useRouter();
  const { profile, user, locale } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canManage = hasPermission(user?.permissions, "students.manage");

  const [names, setNames] = useState<NameValue>({ ...EMPTY_NAME });
  const [sex, setSex] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [studentNumber, setStudentNumber] = useState("");
  const [admissionDate, setAdmissionDate] = useState("");
  const [yearId, setYearId] = useState("");
  const [levelId, setLevelId] = useState("");
  const [sectionId, setSectionId] = useState("");

  const [years, setYears] = useState<AcademicYear[]>([]);
  const [levels, setLevels] = useState<AcademicLevel[]>([]);
  const [sections, setSections] = useState<AcademicSection[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsErrorKey, setOptionsErrorKey] = useState<string | null>(null);

  const [preview, setPreview] = useState<RegistrationPreview | null>(null);
  const [awaitingConfirm, setAwaitingConfirm] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formErrorKey, setFormErrorKey] = useState<string | null>(null);

  const loadOptions = useCallback(async () => {
    if (!profile) return;
    setOptionsLoading(true);
    setOptionsErrorKey(null);
    try {
      const [yearList, levelList] = await Promise.all([
        listYears(profile.instanceId),
        listLevels(profile.instanceId),
      ]);
      setYears(yearList.items);
      setLevels(levelList.items);
    } catch (caught) {
      setOptionsErrorKey(studentErrorKey(caught, "students.register.options_error"));
    } finally {
      setOptionsLoading(false);
    }
  }, [profile?.instanceId]);

  useEffect(() => {
    if (!canManage) return;
    void loadOptions();
  }, [canManage, loadOptions]);

  useEffect(() => {
    if (!profile || !yearId || !levelId) {
      setSections([]);
      return;
    }
    let cancelled = false;
    void listSections(profile.instanceId, yearId, levelId)
      .then((result) => {
        if (!cancelled) setSections(result.items);
      })
      .catch(() => {
        if (!cancelled) setSections([]);
      });
    return () => {
      cancelled = true;
    };
  }, [profile?.instanceId, yearId, levelId]);

  function resetPreview(): void {
    setPreview(null);
    setAwaitingConfirm(false);
  }

  function buildPayload(): StudentRegistration {
    const person = personPayload(names, sex, dateOfBirth);
    person.phone = clean(phone);
    person.address = clean(address);
    const data: StudentRegistration = { person };
    if (studentNumber.trim()) data.student_number = studentNumber.trim();
    if (admissionDate.trim()) data.admission_date = admissionDate.trim();
    if (yearId && levelId) {
      data.enrollment = {
        year_id: yearId,
        level_id: levelId,
        section_id: sectionId || undefined,
      };
    }
    return data;
  }

  async function save(): Promise<void> {
    if (!profile) return;
    setSaving(true);
    setFormErrorKey(null);
    try {
      const student = await registerStudent(profile.instanceId, buildPayload());
      router.replace({
        pathname: "/(app)/students/[studentId]",
        params: { studentId: student.id },
      });
    } catch (caught) {
      setFormErrorKey(studentErrorKey(caught, "students.register.failed"));
    } finally {
      setSaving(false);
    }
  }

  async function submit(): Promise<void> {
    setFormErrorKey(null);
    if (!namesValid(names)) {
      setFormErrorKey("students.register.names_required");
      return;
    }
    if ((yearId && !levelId) || (!yearId && levelId)) {
      setFormErrorKey("students.register.enrollment_incomplete");
      return;
    }
    if (awaitingConfirm) {
      await save();
      return;
    }
    if (!profile) return;
    setPreviewing(true);
    try {
      const result = await previewRegistration(profile.instanceId, buildPayload());
      setPreview(result);
      if (result.duplicate_warnings.length > 0) {
        setAwaitingConfirm(true);
        return;
      }
      await save();
    } catch (caught) {
      setFormErrorKey(studentErrorKey(caught, "students.register.failed"));
    } finally {
      setPreviewing(false);
    }
  }

  if (!canManage) {
    return (
      <Screen colors={colors} testID="student-registration-screen">
        <ErrorState colors={colors} title={t("students.register.permission_denied")} />
      </Screen>
    );
  }

  const sexOptions: SelectOption[] = [
    { value: "", label: t("students.sex.unspecified") },
    { value: "male", label: t("students.sex.male") },
    { value: "female", label: t("students.sex.female") },
  ];
  const yearOptions: SelectOption[] = [
    { value: "", label: t("students.register.no_enrollment") },
    ...years.map((year) => ({ value: year.id, label: year.name })),
  ];
  const levelOptions: SelectOption[] = [
    { value: "", label: t("students.register.no_level") },
    ...levels.map((level) => ({ value: level.id, label: level.name })),
  ];
  const sectionOptions: SelectOption[] = [
    { value: "", label: t("students.register.no_section") },
    ...sections.map((section) => ({
      value: section.id,
      label: section.name ? `${section.code} · ${section.name}` : section.code,
    })),
  ];

  return (
    <Screen colors={colors} testID="student-registration-screen">
      <PageHeader
        colors={colors}
        title={t("students.register.title")}
        subtitle={t("students.register.hint")}
      />
      <Muted colors={colors}>{t("students.register.online_only")}</Muted>

      <Card colors={colors}>
        <NameFields colors={colors} locale={locale} value={names} onChange={setNames} />
        <SelectField
          colors={colors}
          label={t("students.sex")}
          value={sex}
          options={sexOptions}
          onChange={setSex}
          placeholder={t("students.sex.unspecified")}
          testID="register-sex"
        />
        <Field
          colors={colors}
          label={t("students.date_of_birth")}
          placeholder={t("students.date_format")}
          value={dateOfBirth}
          onChangeText={setDateOfBirth}
          autoCapitalize="none"
          testID="register-date-of-birth"
        />
        <Field
          colors={colors}
          label={t("students.phone")}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
          testID="register-phone"
        />
        <Field
          colors={colors}
          label={t("students.address")}
          value={address}
          onChangeText={setAddress}
          testID="register-address"
        />
      </Card>

      <Card colors={colors}>
        <SectionTitle colors={colors}>{t("students.register.enrollment")}</SectionTitle>
        {optionsLoading ? (
          <ActivityIndicator color={colors.primary} />
        ) : optionsErrorKey ? (
          <View style={styles.optionError}>
            <Muted colors={colors}>{t(optionsErrorKey)}</Muted>
            <Button
              colors={colors}
              secondary
              label={t("common.retry")}
              onPress={() => void loadOptions()}
            />
          </View>
        ) : (
          <>
            <SelectField
              colors={colors}
              label={t("students.enrollment.year")}
              value={yearId}
              options={yearOptions}
              onChange={(next) => {
                setYearId(next);
                setLevelId("");
                setSectionId("");
                resetPreview();
              }}
              placeholder={t("students.register.no_enrollment")}
              testID="register-year"
            />
            <SelectField
              colors={colors}
              label={t("students.enrollment.level")}
              value={levelId}
              options={levelOptions}
              onChange={(next) => {
                setLevelId(next);
                setSectionId("");
                resetPreview();
              }}
              placeholder={t("students.register.no_level")}
              disabled={!yearId}
              testID="register-level"
            />
            <SelectField
              colors={colors}
              label={t("students.enrollment.section")}
              value={sectionId}
              options={sectionOptions}
              onChange={(next) => {
                setSectionId(next);
                resetPreview();
              }}
              placeholder={t("students.register.no_section")}
              disabled={!yearId || !levelId}
              testID="register-section"
            />
            {years.length === 0 ? (
              <Muted colors={colors}>{t("students.register.no_year")}</Muted>
            ) : null}
          </>
        )}
      </Card>

      <Card colors={colors}>
        <Field
          colors={colors}
          label={t("students.number")}
          hint={t("students.register.number_hint")}
          value={studentNumber}
          onChangeText={setStudentNumber}
          autoCapitalize="characters"
          testID="register-student-number"
        />
        <Field
          colors={colors}
          label={t("students.admission_date")}
          placeholder={t("students.date_format")}
          value={admissionDate}
          onChangeText={setAdmissionDate}
          autoCapitalize="none"
          testID="register-admission-date"
        />
      </Card>

      {preview && preview.duplicate_warnings.length > 0 ? (
        <Card colors={colors} style={{ borderColor: colors.accent }}>
          <View testID="registration-duplicates">
            <Text style={[styles.duplicateTitle, { color: colors.foreground }]}>
              {t("students.duplicate.title")}
            </Text>
            <Muted colors={colors}>{t("students.duplicate.hint")}</Muted>
            {preview.duplicate_warnings.map((warning, index) => (
              <Text
                key={`${warning.person.full_name ?? "duplicate"}-${index}`}
                style={[styles.duplicateRow, { color: colors.foreground }]}
              >
                {warning.person.full_name ?? ""} —{" "}
                {t("students.duplicate.similarity", {
                  percent: Math.round(warning.similarity * 100),
                })}
              </Text>
            ))}
          </View>
          <Muted colors={colors}>
            {t(
              preview.number_generated
                ? "students.register.number_generated"
                : "students.register.number_manual",
              { number: preview.student_number },
            )}
          </Muted>
        </Card>
      ) : null}

      {formErrorKey ? (
        <Text accessibilityRole="alert" style={[styles.error, { color: colors.destructive }]}>
          {t(formErrorKey)}
        </Text>
      ) : null}

      <Button
        colors={colors}
        label={
          previewing
            ? t("students.register.previewing")
            : saving
              ? t("students.register.saving")
              : awaitingConfirm
                ? t("students.register.anyway")
                : t("students.register.submit")
        }
        busy={previewing || saving}
        onPress={() => void submit()}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  optionError: { gap: 8 },
  duplicateTitle: { fontSize: 16, fontWeight: "600", marginBottom: 4 },
  duplicateRow: { fontSize: 14, marginTop: 6 },
  error: { fontSize: 14 },
});
