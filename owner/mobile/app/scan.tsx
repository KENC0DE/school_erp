import { CameraView, useCameraPermissions } from "expo-camera";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { useApp } from "../src/context/AppContext";
import { parseSchoolQrPayload } from "../src/directory/qr";
import { translateUi } from "../src/i18n/ui-messages";
import { defaultNativeTheme } from "../src/theme/nativeTheme";
import { Button, SafeScreen, Title } from "../src/ui/primitives";

export default function ScanScreen() {
  const router = useRouter();
  const { locale, mode } = useApp();
  const [permission, requestPermission] = useCameraPermissions();
  const [handled, setHandled] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const colors = useMemo(() => defaultNativeTheme(mode).colors, [mode]);
  const ui = (key: Parameters<typeof translateUi>[1]) => translateUi(locale, key);

  function onBarcodeScanned(result: { data: string }): void {
    if (handled) return;
    const code = parseSchoolQrPayload(result.data);
    if (!code) {
      setInvalid(true);
      return;
    }
    setHandled(true);
    router.replace({ pathname: "/", params: { code } });
  }

  return (
    <SafeScreen colors={colors}>
      <View style={styles.header}>
        <Title colors={colors}>{ui("scan.title")}</Title>
        <Text style={[styles.body, { color: colors.mutedForeground }]}>{ui("scan.instructions")}</Text>
      </View>

      {!permission ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : permission.granted ? (
        <View style={styles.cameraWrap}>
          <CameraView
            style={styles.camera}
            facing="back"
            barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
            onBarcodeScanned={handled ? undefined : onBarcodeScanned}
          />
          {invalid ? (
            <Text style={[styles.error, { color: colors.destructive }]}>{ui("scan.invalid")}</Text>
          ) : null}
        </View>
      ) : (
        <View style={styles.center}>
          <View style={[styles.permissionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.permissionTitle, { color: colors.foreground }]}>
              {ui("scan.permissionTitle")}
            </Text>
            <Text style={[styles.body, { color: colors.mutedForeground }]}>{ui("scan.permissionBody")}</Text>
            <Button colors={colors} label={ui("scan.grant")} onPress={() => void requestPermission()} />
            <Text style={[styles.footnote, { color: colors.mutedForeground }]}>{ui("scan.denied")}</Text>
          </View>
        </View>
      )}

      <View style={styles.footer}>
        <Button colors={colors} secondary label={ui("scan.close")} onPress={() => router.back()} />
      </View>
    </SafeScreen>
  );
}

const styles = StyleSheet.create({
  header: { padding: 22, paddingBottom: 10 },
  body: { fontSize: 15, lineHeight: 22 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 22 },
  cameraWrap: { flex: 1, marginHorizontal: 16, borderRadius: 16, overflow: "hidden" },
  camera: { flex: 1 },
  error: { fontSize: 14, padding: 10 },
  permissionCard: { borderWidth: 1, borderRadius: 14, padding: 18, gap: 12, width: "100%" },
  permissionTitle: { fontSize: 18, fontWeight: "700" },
  footnote: { fontSize: 12 },
  footer: { padding: 18 },
});
