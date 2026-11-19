import { useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { useApp } from "../../../src/context/AppContext";
import { useSchoolI18n } from "../../../src/i18n/SchoolI18nContext";
import { listStudents } from "../../../src/students/api";
import { studentErrorKey } from "../../../src/students/errors";
import { hasPermission } from "../../../src/students/permissions";
import { statusTone } from "../../../src/students/status";
import {
  STUDENT_STATUSES,
  type StudentFilters,
  type StudentSummary,
} from "../../../src/students/types";
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

export default function StudentsScreen() {
  const router = useRouter();
  const { profile, user } = useApp();
  const { t } = useSchoolI18n();
  const { rn } = useSchoolThemeContext();
  const colors = rn.colors;

  const canView = hasPermission(user?.permissions, "students.view");
  const canManage = hasPermission(user?.permissions, "students.manage");

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [filters, setFilters] = useState<StudentFilters>({});
  const [items, setItems] = useState<StudentSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(
    async (nextFilters: StudentFilters, nextCursor: string | null, append: boolean) => {
      if (!profile) return;
      const id = requestId.current + 1;
      requestId.current = id;
      if (append) setLoadingMore(true);
      else setLoading(true);
      setErrorKey(null);
      try {
        const data = await listStudents(profile.instanceId, nextFilters, nextCursor);
        if (id !== requestId.current) return;
        setItems((current) => (append ? [...current, ...data.items] : data.items));
        setCursor(data.next_cursor);
        setTotal(data.total);
      } catch (caught) {
        if (id === requestId.current) {
          setErrorKey(studentErrorKey(caught, "students.load_error"));
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

  function openStudent(student: StudentSummary): void {
    router.push({
      pathname: "/(app)/students/[studentId]",
      params: { studentId: student.id },
    });
  }

  function openRegister(): void {
    router.push("/(app)/students/new");
  }

  const statusOptions: SelectOption[] = [
    { value: "", label: t("students.filter.all_statuses") },
    ...STUDENT_STATUSES.map((value) => ({
      value,
      label: t(`students.status.${value}`),
    })),
  ];

  const registerAction = canManage ? (
    <Button colors={colors} label={t("students.register.open")} onPress={openRegister} />
  ) : undefined;

  return (
    <Screen colors={colors} testID="students-screen">
      <PageHeader
        colors={colors}
        title={t("students.title")}
        subtitle={t("students.count", { count: total })}
      />

      {!canView ? (
        <ErrorState colors={colors} title={t("students.permission_denied")} />
      ) : (
        <>
          <Field
            colors={colors}
            label={t("students.search.label")}
            placeholder={t("students.search.placeholder")}
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={search}
            returnKeyType="search"
            autoCapitalize="none"
            testID="students-search"
          />
          <SelectField
            colors={colors}
            label={t("students.status")}
            value={status}
            options={statusOptions}
            onChange={changeStatus}
            placeholder={t("students.filter.all_statuses")}
            testID="students-status-filter"
          />
          <Button colors={colors} secondary label={t("students.search.action")} onPress={search} />

          {loading && items.length === 0 ? (
            <View style={styles.state}>
              <ActivityIndicator color={colors.primary} />
              <Muted colors={colors}>{t("students.loading")}</Muted>
            </View>
          ) : errorKey && items.length === 0 ? (
            <ErrorState
              colors={colors}
              title={t("students.load_error")}
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
              title={t("students.empty")}
              description={t("students.empty_hint")}
              action={registerAction}
            />
          ) : (
            <Card colors={colors} style={styles.list}>
              {items.map((student) => {
                const placement = student.enrollment
                  ? [student.enrollment.level_name, student.enrollment.section_code]
                      .filter(Boolean)
                      .join(" · ")
                  : t("students.not_enrolled");
                return (
                  <ListRow
                    key={student.id}
                    colors={colors}
                    testID={`student-row-${student.id}`}
                    title={student.person.full_name}
                    subtitle={`${student.student_number} · ${placement}`}
                    right={
                      <Badge colors={colors} tone={statusTone(student.status)}>
                        {t(`students.status.${student.status}`)}
                      </Badge>
                    }
                    onPress={() => openStudent(student)}
                  />
                );
              })}
              {errorKey ? <Muted colors={colors}>{t(errorKey)}</Muted> : null}
              {cursor ? (
                <Button
                  colors={colors}
                  secondary
                  label={t("students.directory.load_more")}
                  busy={loadingMore}
                  onPress={loadMore}
                />
              ) : null}
            </Card>
          )}

          {registerAction}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  state: { alignItems: "center", gap: 8, paddingVertical: 24 },
  list: { paddingVertical: 0, paddingHorizontal: 0 },
});
