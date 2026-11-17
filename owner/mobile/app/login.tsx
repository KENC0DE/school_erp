import { Redirect, useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { ActivityIndicator, Image, ScrollView, StyleSheet, Text, View } from "react-native";

import { useApp } from "../src/context/AppContext";
import { translateUi, type UiKey } from "../src/i18n/ui-messages";
import { SessionError } from "../src/session/session";
import { useSchoolTheme } from "../src/theme/useSchoolTheme";
import { Button, Card, Field, SafeScreen, Title } from "../src/ui/primitives";

function errorKeyFor(error: unknown): UiKey {
  if (error instanceof SessionError) {
    if (error.code === "INVALID_CREDENTIALS" || error.code === "UNAUTHORIZED" || error.code === "auth.invalid") {
      return "login.invalid";
    }
    if (error.code === "NETWORK_ERROR") return "login.network";
  }
  return "login.failed";
}

export default function LoginScreen() {
  const router = useRouter();
  const { ready, profile, user, locale, mode, signIn } = useApp();
  const schoolTheme = useSchoolTheme(profile, mode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorKey, setErrorKey] = useState<UiKey | null>(null);
  const colors = schoolTheme.rn.colors;
  const ui = useMemo(
    () => (key: UiKey, values: Record<string, string | number> = {}) => translateUi(locale, key, values),
    [locale],
  );

  async function submit(): Promise<void> {
    setErrorKey(null);
    setBusy(true);
    try {
      await signIn(email, password);
      router.replace("/(app)");
    } catch (caught) {
      setErrorKey(errorKeyFor(caught));
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

  if (!profile) return <Redirect href="/" />;
  if (user) return <Redirect href="/(app)" />;

  return (
    <SafeScreen colors={colors}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.school}>
          {profile.logoUrl ? (
            <Image source={{ uri: profile.logoUrl }} style={styles.logo} />
          ) : (
            <View style={[styles.logo, styles.logoFallback, { backgroundColor: colors.muted }]}>
              <Text style={[styles.logoLetter, { color: colors.foreground }]}>
                {profile.name.slice(0, 1).toUpperCase()}
              </Text>
            </View>
          )}
          <View style={styles.schoolText}>
            <Text style={[styles.schoolName, { color: colors.foreground }]}>{profile.name}</Text>
            <Text style={[styles.muted, { color: colors.mutedForeground }]}>{profile.apiBaseUrl}</Text>
          </View>
        </View>

        <Card colors={colors} style={styles.card}>
          <Title colors={colors}>{ui("login.submit")}</Title>
          <Text style={[styles.muted, { color: colors.mutedForeground }]}>{ui("login.subtitle")}</Text>
          <Field
            colors={colors}
            label={ui("login.email")}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="emailAddress"
            placeholder={ui("login.email")}
          />
          <Field
            colors={colors}
            label={ui("login.password")}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            textContentType="password"
            placeholder={ui("login.password")}
            onSubmitEditing={() => void submit()}
          />
          {errorKey ? <Text style={[styles.error, { color: colors.destructive }]}>{ui(errorKey)}</Text> : null}
          <Button
            colors={colors}
            label={busy ? ui("login.submitting") : ui("login.submit")}
            busy={busy}
            disabled={email.trim() === "" || password === ""}
            onPress={() => void submit()}
          />
        </Card>

        <View style={styles.change}>
          <Button
            colors={colors}
            secondary
            label={ui("login.chooseSchool")}
            onPress={() => router.replace("/")}
          />
        </View>
      </ScrollView>
    </SafeScreen>
  );
}

const styles = StyleSheet.create({
  content: { padding: 22, paddingBottom: 40, flexGrow: 1, justifyContent: "center" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  school: { flexDirection: "row", alignItems: "center", gap: 14, marginBottom: 24 },
  schoolText: { flex: 1 },
  schoolName: { fontSize: 20, fontWeight: "700" },
  logo: { width: 54, height: 54, borderRadius: 12 },
  logoFallback: { alignItems: "center", justifyContent: "center" },
  logoLetter: { fontSize: 22, fontWeight: "700" },
  card: { gap: 10 },
  muted: { fontSize: 14, marginBottom: 12 },
  error: { fontSize: 14, marginBottom: 8 },
  change: { marginTop: 16 },
});
