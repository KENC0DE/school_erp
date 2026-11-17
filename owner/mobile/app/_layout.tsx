import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AppProvider, useApp } from "../src/context/AppContext";

function RootStack() {
  const { mode } = useApp();
  return (
    <>
      <StatusBar style={mode === "dark" ? "light" : "dark"} />
      <Stack screenOptions={{ headerShown: false }} />
    </>
  );
}

export default function RootLayout() {
  // The Ethiopic face ships inside the app bundle, so Amharic labels render the
  // same everywhere instead of depending on an OS font (P1-20).
  const [fontsLoaded] = useFonts({
    // Metro resolves font assets from a static require, not from import.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    NotoSansEthiopic: require("../assets/fonts/NotoSansEthiopic-Regular.ttf"),
  });
  if (!fontsLoaded) return null;
  return (
    <SafeAreaProvider>
      <AppProvider>
        <RootStack />
      </AppProvider>
    </SafeAreaProvider>
  );
}
