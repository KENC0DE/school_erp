import { useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useApp } from "../../../src/context/AppContext";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import { listStaff } from "../../../src/staff/api";
import { staffErrorKey } from "../../../src/staff/errors";
import { hasPermission } from "../../../src/staff/permissions";
import { statusTone } from "../../../src/staff/status";
import { STAFF_STATUSES, type StaffFilters, type StaffSummary } from "../../../src/staff/types";
import { useSchoolThemeContext } from "../../../src/theme/SchoolThemeContext";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  ListRow,
  Muted,
  PageHeader,
  Screen,
  SelectField,
  type SelectOption,
} from "../../../src/ui";

export default function StaffScreen() {
  const router = useRouter();
  const { profile, user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canView = hasPermission(user?.permissions, "staff.view");

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [filters, setFilters] = useState<StaffFilters>({});
  const [items, setItems] = useState<StaffSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(
    async (nextFilters: StaffFilters, nextCursor: string | null, append: boolean) => {
      if (!profile) return;
      const id = requestId.current + 1;
      requestId.current = id;
      if (append) setLoadingMore(true);
      else setLoading(true);
      setErrorKey(null);
      try {
        const data = await listStaff(profile.instanceId, nextFilters, nextCursor);
        if (id !== requestId.current) return;
        setItems((current) => (append ? [...current, ...data.items] : data.items));
        setCursor(data.next_cursor);
        setTotal(data.total);
      } catch (caught) {
        if (id === requestId.current) {
          setErrorKey(staffErrorKey(caught, "staff.load_error"));
        }
      } finally {
        if (id === requestId.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [profile?.instanceId],
  );

  useEffect(() => {
    if (!canView) {
      setLoading(false);
      return;
    }
    void load(filters, null, false);
  }, [canView, filters, load]);

  function search(): void {
    setFilters({ q: query.trim() || undefined, status: status || undefined });
  }

  function changeStatus(next: string): void {
    setStatus(next);
    setFilters({ q: query.trim() || undefined, status: next || undefined });
  }

  function loadMore(): void {
    if (cursor) void load(filters, cursor, true);
  }

  function openStaff(member: StaffSummary): void {
    router.push({
      pathname: "/(app)/staff/[staffId]",
      params: { staffId: member.id },
    });
  }

  const statusOptions: SelectOption[] = [
    { value: "", label: t("staff.filter.all_statuses") },
    ...STAFF_STATUSES.map((value) => ({
      value,
      label: t(`staff.status.${value}`),
    })),
  ];

  return (
    <Screen colors={colors} testID="staff-screen">
      <PageHeader
        colors={colors}
        title={t("staff.title")}
        subtitle={t("staff.count", { count: total })}
      />

      {!canView ? (
        <ErrorState colors={colors} title={t("staff.permission_denied")} />
      ) : (
        <>
          <Field
            colors={colors}
            label={t("staff.search.label")}
            placeholder={t("staff.search.placeholder")}
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={search}
            returnKeyType="search"
            autoCapitalize="none"
            testID="staff-search"
          />
          <SelectField
            colors={colors}
            label={t("staff.status")}
            value={status}
            options={statusOptions}
            onChange={changeStatus}
            placeholder={t("staff.filter.all_statuses")}
            testID="staff-status-filter"
          />
          <Button
            colors={colors}
            secondary
            label={t("staff.search.action")}
            onPress={search}
          />

          {loading && items.length === 0 ? (
            <View style={styles.state}>
              <ActivityIndicator color={colors.primary} />
              <Muted colors={colors}>{t("staff.loading")}</Muted>
            </View>
          ) : errorKey && items.length === 0 ? (
            <ErrorState
              colors={colors}
              title={t("staff.load_error")}
              description={t(errorKey)}
              action={
                <Button
                  colors={colors}
                  secondary
                  label={t("common.retry")}
                  onPress={() => void load(filters, null, false)}
                />
              }
            />
          ) : items.length === 0 ? (
            <EmptyState
              colors={colors}
              title={t("staff.empty")}
              description={t("staff.empty_hint")}
            />
          ) : (
            <Card colors={colors} style={styles.list}>
              {items.map((member) => {
                const placement = [member.department?.name, member.position?.name]
                  .filter(Boolean)
                  .join(" · ");
                return (
                  <ListRow
                    key={member.id}
                    colors={colors}
                    testID={`staff-row-${member.id}`}
                    title={member.person.full_name}
                    subtitle={`${member.staff_number}${placement ? ` · ${placement}` : ""}`}
                    right={
                      <Badge colors={colors} tone={statusTone(member.status)}>
                        {t(`staff.status.${member.status}`)}
                      </Badge>
                    }
                    onPress={() => openStaff(member)}
                  />
                );
              })}
              {errorKey ? <Muted colors={colors}>{t(errorKey)}</Muted> : null}
              {cursor ? (
                <Button
                  colors={colors}
                  secondary
                  label={t("staff.directory.load_more")}
                  busy={loadingMore}
                  onPress={loadMore}
                />
              ) : null}
            </Card>
          )}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  state: { alignItems: "center", gap: 8, paddingVertical: 24 },
  list: { paddingVertical: 0, paddingHorizontal: 0 },
});
