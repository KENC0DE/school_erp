import { useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useApp } from "../../../src/context/AppContext";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import { getStaff } from "../../../src/staff/api";
import { staffErrorKey } from "../../../src/staff/errors";
import { hasPermission } from "../../../src/staff/permissions";
import { statusTone } from "../../../src/staff/status";
import type { StaffDetail } from "../../../src/staff/types";
import { useSchoolThemeContext } from "../../../src/theme/SchoolThemeContext";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Muted,
  PageHeader,
  Row,
  Screen,
  SectionTitle,
  type Palette,
} from "../../../src/ui";

function detailValue(colors: Palette, value: string | null, notSet: string) {
  return value ? value : <Muted colors={colors}>{notSet}</Muted>;
}

export default function StaffProfileScreen() {
  const router = useRouter();
  const { staffId } = useLocalSearchParams<{ staffId?: string }>();
  const { profile, user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canView = hasPermission(user?.permissions, "staff.view");

  const [detail, setDetail] = useState<StaffDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorKey, setErrorKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!profile || !staffId) {
      setLoading(false);
      setErrorKey("staff.profile_error");
      return;
    }
    setLoading(true);
    setErrorKey(null);
    try {
      setDetail(await getStaff(profile.instanceId, staffId));
    } catch (caught) {
      setErrorKey(staffErrorKey(caught, "staff.profile_error"));
    } finally {
      setLoading(false);
    }
  }, [profile?.instanceId, staffId]);

  useEffect(() => {
    if (!canView) {
      setLoading(false);
      return;
    }
    void load();
  }, [canView, load]);

  function backToList(): void {
    router.push("/(app)/staff");
  }

  if (!canView) {
    return (
      <Screen colors={colors} testID="staff-profile-screen">
        <ErrorState colors={colors} title={t("staff.permission_denied")} />
      </Screen>
    );
  }

  if (loading) {
    return (
      <Screen colors={colors} testID="staff-profile-screen">
        <View style={styles.state}>
          <ActivityIndicator color={colors.primary} />
          <Muted colors={colors}>{t("staff.profile.loading")}</Muted>
        </View>
      </Screen>
    );
  }

  if (errorKey || !detail) {
    return (
      <Screen colors={colors} testID="staff-profile-screen">
        <ErrorState
          colors={colors}
          title={t("staff.profile_error")}
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
        <Button colors={colors} secondary label={t("staff.back_to_list")} onPress={backToList} />
      </Screen>
    );
  }

  const person = detail.person;
  const amharicName = [person.given_name_am, person.father_name_am, person.grandfather_name_am]
    .filter(Boolean)
    .join(" ");

  return (
    <Screen colors={colors} testID="staff-profile-screen">
      <Button colors={colors} secondary label={t("staff.back_to_list")} onPress={backToList} />
      <PageHeader
        colors={colors}
        title={person.full_name}
        subtitle={amharicName || detail.staff_number}
      />

      <Card colors={colors}>
        <Row colors={colors} label={t("staff.staff_number")} value={detail.staff_number} />
        <Row
          colors={colors}
          label={t("staff.status")}
          value={
            <Badge colors={colors} tone={statusTone(detail.status)}>
              {t(`staff.status.${detail.status}`)}
            </Badge>
          }
        />
        <Row
          colors={colors}
          label={t("staff.department")}
          value={detailValue(colors, detail.department?.name ?? null, t("staff.not_set"))}
        />
        <Row
          colors={colors}
          label={t("staff.position")}
          value={detailValue(colors, detail.position?.name ?? null, t("staff.not_set"))}
        />
        <Row
          colors={colors}
          label={t("staff.hire_date")}
          value={detailValue(colors, detail.hire_date, t("staff.not_set"))}
        />
      </Card>

      <SectionTitle colors={colors}>{t("staff.person")}</SectionTitle>
      <Card colors={colors}>
        <Row
          colors={colors}
          label={t("staff.person.phone")}
          value={detailValue(colors, person.phone, t("staff.not_set"))}
        />
        <Row
          colors={colors}
          label={t("staff.person.email")}
          value={detailValue(colors, person.email, t("staff.not_set"))}
        />
        <Row
          colors={colors}
          label={t("staff.person.address")}
          value={detailValue(colors, person.address, t("staff.not_set"))}
        />
        <Row
          colors={colors}
          label={t("staff.notes")}
          value={detailValue(colors, detail.notes, t("staff.not_set"))}
        />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  state: { alignItems: "center", gap: 8, paddingVertical: 24 },
});
