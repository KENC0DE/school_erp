import { useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useApp } from "../../../src/context/AppContext";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import { getStudent } from "../../../src/students/api";
import { studentErrorKey } from "../../../src/students/errors";
import { hasPermission } from "../../../src/students/permissions";
import { statusTone } from "../../../src/students/status";
import type { StudentDetail } from "../../../src/students/types";
import { useSchoolThemeContext } from "../../../src/theme/SchoolThemeContext";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Muted,
  PageHeader,
  Row,
  Screen,
  SectionTitle,
  type Palette,
} from "../../../src/ui";

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function detailValue(colors: Palette, value: string | null, notSet: string) {
  return value ? value : <Muted colors={colors}>{notSet}</Muted>;
}

export default function StudentProfileScreen() {
  const router = useRouter();
  const { studentId } = useLocalSearchParams<{ studentId?: string }>();
  const { profile, user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canView = hasPermission(user?.permissions, "students.view");
  const canViewMedical = hasPermission(user?.permissions, "students.medical.view");

  const [detail, setDetail] = useState<StudentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!profile || !studentId) {
      setLoading(false);
      setErrorKey("students.profile_error");
      return;
    }
    setLoading(true);
    setErrorKey(null);
    try {
      setDetail(await getStudent(profile.instanceId, studentId));
    } catch (caught) {
      setErrorKey(studentErrorKey(caught, "students.profile_error"));
    } finally {
      setLoading(false);
    }
  }, [profile?.instanceId, studentId]);

  useEffect(() => {
    if (!canView) {
      setLoading(false);
      return;
    }
    void load();
  }, [canView, load]);

  function backToList(): void {
    router.push("/(app)/students");
  }

  if (!canView) {
    return (
      <Screen colors={colors} testID="student-profile-screen">
        <ErrorState colors={colors} title={t("students.permission_denied")} />
      </Screen>
    );
  }

  if (loading) {
    return (
      <Screen colors={colors} testID="student-profile-screen">
        <View style={styles.state}>
          <ActivityIndicator color={colors.primary} />
          <Muted colors={colors}>{t("students.profile.loading")}</Muted>
        </View>
      </Screen>
    );
  }

  if (errorKey || !detail) {
    return (
      <Screen colors={colors} testID="student-profile-screen">
        <ErrorState
          colors={colors}
          title={t("students.profile_error")}
          description={errorKey ? t(errorKey) : undefined}
          action={
            <Button
              colors={colors}
              secondary
              label={t("common.retry")}
              onPress={() => void load()}
            />
          }
        />
        <Button colors={colors} secondary label={t("students.back_to_list")} onPress={backToList} />
      </Screen>
    );
  }

  const person = detail.person;
  const amharicName = [person.given_name_am, person.father_name_am, person.grandfather_name_am]
    .filter(Boolean)
    .join(" ");
  const medical = detail.medical;

  return (
    <Screen colors={colors} testID="student-profile-screen">
      <Button colors={colors} secondary label={t("students.back_to_list")} onPress={backToList} />
      <PageHeader
        colors={colors}
        title={person.full_name}
        subtitle={amharicName || detail.student_number}
      />

      <Card colors={colors}>
        <Row colors={colors} label={t("students.number")} value={detail.student_number} />
        <Row
          colors={colors}
          label={t("students.status")}
          value={
            <Badge colors={colors} tone={statusTone(detail.status)}>
              {t(`students.status.${detail.status}`)}
            </Badge>
          }
        />
        <Row
          colors={colors}
          label={t("students.date_of_birth")}
          value={detailValue(colors, person.date_of_birth, t("students.not_set"))}
        />
        <Row
          colors={colors}
          label={t("students.sex")}
          value={person.sex ? t(`students.sex.${person.sex}`) : t("students.not_set")}
        />
        <Row
          colors={colors}
          label={t("students.phone")}
          value={detailValue(colors, person.phone, t("students.not_set"))}
        />
        <Row
          colors={colors}
          label={t("students.email")}
          value={detailValue(colors, person.email, t("students.not_set"))}
        />
        <Row
          colors={colors}
          label={t("students.address")}
          value={detailValue(colors, person.address, t("students.not_set"))}
        />
        <Row
          colors={colors}
          label={t("students.admission_date")}
          value={detailValue(colors, detail.admission_date, t("students.not_set"))}
        />
        <Row
          colors={colors}
          label={t("students.enrollment")}
          value={
            detail.enrollment
              ? [detail.enrollment.level_name, detail.enrollment.section_code]
                  .filter(Boolean)
                  .join(" · ")
              : t("students.not_enrolled")
          }
        />
        <Row
          colors={colors}
          label={t("students.notes")}
          value={detailValue(colors, detail.notes, t("students.not_set"))}
          last
        />
      </Card>

      <SectionTitle colors={colors}>{t("students.enrollments")}</SectionTitle>
      {detail.enrollments.length === 0 ? (
        <EmptyState colors={colors} title={t("students.enrollments.empty")} />
      ) : (
        <Card colors={colors}>
          {detail.enrollments.map((enrollment) => {
            const year = enrollment.year_name ?? enrollment.year_code ?? t("students.not_set");
            const level = enrollment.level_name ?? enrollment.level_code ?? t("students.not_set");
            const section = enrollment.section_code ?? t("students.not_set");
            const roll = enrollment.roll_number ? ` · ${enrollment.roll_number}` : "";
            return (
              <Row
                key={enrollment.id}
                colors={colors}
                label={year}
                value={`${level} · ${section}${roll}`}
              />
            );
          })}
        </Card>
      )}

      <SectionTitle colors={colors}>{t("students.guardians")}</SectionTitle>
      {detail.guardians.length === 0 ? (
        <EmptyState colors={colors} title={t("students.guardian.empty")} />
      ) : (
        <Card colors={colors}>
          {detail.guardians.map((guardian) => {
            const relationship = t(`students.relationship.${guardian.relationship}`);
            const subtitle = guardian.is_primary
              ? `${relationship} · ${t("students.guardian.primary")}`
              : relationship;
            return (
              <Row
                key={guardian.id}
                colors={colors}
                label={subtitle}
                value={guardian.person.full_name}
              />
            );
          })}
        </Card>
      )}

      {canViewMedical ? (
        <>
          <SectionTitle colors={colors}>{t("students.medical")}</SectionTitle>
          <Card colors={colors}>
            {medical ? (
              <>
                <Row
                  colors={colors}
                  label={t("students.medical.blood_type")}
                  value={detailValue(colors, text(medical.blood_type), t("students.not_set"))}
                />
                <Row
                  colors={colors}
                  label={t("students.medical.allergies")}
                  value={detailValue(colors, text(medical.allergies), t("students.not_set"))}
                />
                <Row
                  colors={colors}
                  label={t("students.medical.chronic_conditions")}
                  value={detailValue(
                    colors,
                    text(medical.chronic_conditions),
                    t("students.not_set"),
                  )}
                />
                <Row
                  colors={colors}
                  label={t("students.medical.medications")}
                  value={detailValue(colors, text(medical.medications), t("students.not_set"))}
                />
                <Row
                  colors={colors}
                  label={t("students.medical.emergency_contact_name")}
                  value={detailValue(
                    colors,
                    text(medical.emergency_contact_name),
                    t("students.not_set"),
                  )}
                />
                <Row
                  colors={colors}
                  label={t("students.medical.emergency_contact_phone")}
                  value={detailValue(
                    colors,
                    text(medical.emergency_contact_phone),
                    t("students.not_set"),
                  )}
                />
                <Row
                  colors={colors}
                  label={t("students.medical.consent_to_treat")}
                  value={medical.consent_to_treat ? t("students.yes") : t("students.no")}
                  last
                />
              </>
            ) : (
              <Muted colors={colors}>{t("students.not_set")}</Muted>
            )}
          </Card>
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  state: { alignItems: "center", gap: 8, paddingVertical: 32 },
});
