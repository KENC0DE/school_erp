import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { controllerBaseUrl } from "../src/config/env";
import { useApp } from "../src/context/AppContext";
import { resolveSchoolCode } from "../src/directory/client";
import { normaliseSchoolCode, parseSchoolQrPayload } from "../src/directory/qr";
import { DirectoryError } from "../src/directory/verify";
import { translateUi, type UiKey } from "../src/i18n/ui-messages";
import { storeVerifiedProfile } from "../src/storage/schoolStorage";
import { defaultNativeTheme } from "../src/theme/nativeTheme";
import { Button, Card, Field, SafeScreen, Title, font, radius, space, text, weight } from "../src/ui";

interface SuspendedSchool {
  name: string;
}

function errorKeyFor(error: unknown): UiKey {
  if (error instanceof DirectoryError) {
    switch (error.code) {
      case "INVALID_CODE":
        return "error.invalid_code";
      case "NOT_FOUND":
        return "error.not_found";
      case "RATE_LIMITED":
        return "error.rate_limited";
      case "NETWORK_ERROR":
        return "error.network";
      case "INVALID_SIGNATURE":
        return "error.invalid_signature";
      case "UNKNOWN_KID":
        return "error.unknown_kid";
      case "EXPIRED":
        return "error.expired";
      case "UNSUPPORTED_URL":
        return "error.unsupported_url";
      case "MALFORMED_RECORD":
      case "MALFORMED_TOKEN":
      case "FIELD_MISMATCH":
      case "BAD_KEY":
      case "ISSUED_IN_FUTURE":
      case "INVALID_RESPONSE":
      case "UNSUPPORTED_ALGORITHM":
        return "error.malformed";
      default:
        return "error.generic";
    }
  }
  return "error.generic";
}

export default function SchoolPickerScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ code?: string }>();
  const { ready, profile, profiles, user, locale, mode, activateProfile, removeSavedProfile, refreshProfiles } =
    useApp();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorKey, setErrorKey] = useState<UiKey | null>(null);
  const [suspended, setSuspended] = useState<SuspendedSchool | null>(null);

  const rn = useMemo(() => defaultNativeTheme(mode), [mode]);
  const colors = rn.colors;
  const ui = (key: UiKey, values: Record<string, string | number> = {}) =>
    translateUi(locale, key, values);

  useEffect(() => {
    if (typeof params.code === "string" && params.code !== "") setValue(params.code);
  }, [params.code]);

  useEffect(() => {
    if (ready && profile && user && !suspended) router.replace("/(app)");
  }, [ready, profile, user, suspended, router]);

  async function submit(): Promise<void> {
    setErrorKey(null);
    setSuspended(null);
    const scanned = parseSchoolQrPayload(value);
    const code = scanned ?? normaliseSchoolCode(value);
    if (!code) {
      setErrorKey("error.invalid_code");
      return;
    }
    setBusy(true);
    try {
      const resolved = await resolveSchoolCode(code);
      await storeVerifiedProfile(resolved.record);
      await activateProfile(resolved.instanceId);
      await refreshProfiles();
      router.push("/login");
    } catch (caught) {
      if (caught instanceof DirectoryError && caught.code === "SUSPENDED") {
        setSuspended({ name: caught.payload?.name ?? code });
      } else {
        setErrorKey(errorKeyFor(caught));
      }
    } finally {
      setBusy(false);
    }
  }

  async function chooseSaved(instanceId: string): Promise<void> {
    setBusy(true);
    setErrorKey(null);
    try {
      await activateProfile(instanceId);
      router.push("/login");
    } catch {
      setErrorKey("error.generic");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return (
      <SafeScreen colors={colors}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      </SafeScreen>
    );
  }

  if (suspended) {
    return (
      <SafeScreen colors={colors}>
        <View style={styles.suspended}>
          <Title colors={colors}>{ui("picker.suspendedTitle")}</Title>
          <Text style={[styles.body, { color: colors.mutedForeground }]}>
            {ui("picker.suspendedBody", { name: suspended.name })}
          </Text>
          <Button colors={colors} label={ui("picker.back")} onPress={() => setSuspended(null)} />
        </View>
      </SafeScreen>
    );
  }

  return (
    <SafeScreen colors={colors}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.brand}>
          <Text style={[styles.eyebrow, { color: colors.primary }]}>{ui("picker.eyebrow")}</Text>
          <Title colors={colors}>{ui("app.name")}</Title>
          <Text style={[styles.tagline, { color: colors.mutedForeground }]}>{ui("app.tagline")}</Text>
        </View>

        <Card colors={colors} style={styles.form}>
          <View style={styles.formText}>
            <Text accessibilityRole="header" style={[styles.subtitle, { color: colors.foreground }]}>
              {ui("picker.title")}
            </Text>
            <Text style={[styles.body, { color: colors.mutedForeground }]}>{ui("picker.subtitle")}</Text>
          </View>
          <Field
            colors={colors}
            label={ui("picker.codeLabel")}
            placeholder={ui("picker.codePlaceholder")}
            autoCapitalize="characters"
            autoCorrect={false}
            value={value}
            onChangeText={setValue}
            onSubmitEditing={() => void submit()}
          />
          {errorKey ? (
            <Text accessibilityLiveRegion="polite" style={[styles.error, { color: colors.destructive }]}>
              {ui(errorKey)}
            </Text>
          ) : null}
          <View style={styles.buttonRow}>
            <View style={styles.grow}>
              <Button
                colors={colors}
                label={busy ? ui("picker.resolving") : ui("picker.continue")}
                busy={busy}
                onPress={() => void submit()}
              />
            </View>
            <View style={styles.grow}>
              <Button
                colors={colors}
                secondary
                label={ui("picker.scan")}
                onPress={() => router.push("/scan")}
              />
            </View>
          </View>
          <Text style={[styles.footnote, { color: colors.mutedForeground }]}>
            {ui("picker.controller", { url: controllerBaseUrl() })}
          </Text>
        </Card>

        <Text accessibilityRole="header" style={[styles.section, { color: colors.foreground }]}>
          {ui("picker.saved")}
        </Text>
        {profiles.length === 0 ? (
          <Text style={[styles.empty, { color: colors.mutedForeground }]}>{ui("picker.noSaved")}</Text>
        ) : (
          profiles.map((saved) => (
            <Card colors={colors} key={saved.instanceId} style={styles.savedCard}>
              <View style={styles.savedRow}>
                <Pressable style={styles.savedMain} onPress={() => void chooseSaved(saved.instanceId)}>
                  {saved.logoUrl ? (
                    <Image source={{ uri: saved.logoUrl }} style={styles.logo} />
                  ) : (
                    <View style={[styles.logo, styles.logoFallback, { backgroundColor: colors.muted }]}>
                      <Text style={[styles.logoLetter, { color: colors.foreground }]}>
                        {saved.name.slice(0, 1).toUpperCase()}
                      </Text>
                    </View>
                  )}
                  <View style={styles.savedText}>
                    <Text style={[styles.savedName, { color: colors.foreground }]}>{saved.name}</Text>
                    <Text style={[styles.footnote, { color: colors.mutedForeground }]}>
                      {saved.apiBaseUrl}
                    </Text>
                  </View>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`${ui("picker.remove")} ${saved.name}`}
                  style={styles.remove}
                  onPress={() => void removeSavedProfile(saved.instanceId)}
                >
                  <Text style={[styles.removeLabel, { color: colors.destructive }]}>
                    {ui("picker.remove")}
                  </Text>
                </Pressable>
              </View>
            </Card>
          ))
        )}
      </ScrollView>
    </SafeScreen>
  );
}

const styles = StyleSheet.create({
  content: { padding: space.base, paddingBottom: space["2xl"], gap: space.base },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  suspended: { flex: 1, justifyContent: "center", padding: space.lg, gap: space.base },
  brand: { gap: space.xs },
  eyebrow: {
    fontSize: text.xs,
    fontWeight: weight.semibold,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    fontFamily: font.family,
  },
  tagline: { fontSize: text.base, lineHeight: 24, fontFamily: font.family },
  form: { gap: space.md },
  formText: { gap: space.xs },
  subtitle: { fontSize: text.lg, fontWeight: weight.semibold, fontFamily: font.family },
  body: { fontSize: text.sm, lineHeight: 21, fontFamily: font.family },
  error: { fontSize: text.sm, fontFamily: font.family },
  buttonRow: { flexDirection: "row", gap: space.sm, marginTop: space.xs },
  grow: { flex: 1 },
  footnote: { fontSize: text.xs, marginTop: space.sm, fontFamily: font.family },
  section: {
    fontSize: text.md,
    fontWeight: weight.semibold,
    marginTop: space.sm,
    fontFamily: font.family,
  },
  empty: { fontSize: text.sm, lineHeight: 21, fontFamily: font.family },
  savedCard: { padding: 0, gap: 0 },
  savedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingHorizontal: space.base,
    paddingVertical: space.md,
  },
  savedMain: { flex: 1, flexDirection: "row", alignItems: "center", gap: space.md },
  savedText: { flex: 1 },
  savedName: { fontSize: text.base, fontWeight: weight.medium, fontFamily: font.family },
  logo: { width: 40, height: 40, borderRadius: radius.md },
  logoFallback: { alignItems: "center", justifyContent: "center" },
  logoLetter: { fontSize: text.base, fontWeight: weight.semibold, fontFamily: font.family },
  remove: { minHeight: 44, justifyContent: "center", paddingHorizontal: space.sm },
  removeLabel: { fontSize: text.sm, fontWeight: weight.medium, fontFamily: font.family },
});
