import type { ExpoConfig } from "expo/config";

// Store metadata and the OS permission prompt live in app config, which Expo
// evaluates outside the app bundle. UI strings remain in src/i18n/ui-messages.
const APP_NAME = "School ERP";
const CAMERA_PERMISSION = "Allow the app to scan school QR codes.";

const config: ExpoConfig = {
  name: APP_NAME,
  slug: "erp-mobile",
  scheme: "erpapp",
  version: "0.1.0",
  orientation: "portrait",
  userInterfaceStyle: "automatic",
  ios: {
    supportsTablet: true,
    bundleIdentifier: "com.erp.mobile",
  },
  android: {
    package: "com.erp.mobile",
  },
  plugins: [
    "expo-router",
    "expo-secure-store",
    [
      "expo-camera",
      {
        cameraPermission: CAMERA_PERMISSION,
      },
    ],
  ],
  experiments: {
    typedRoutes: false,
  },
};

export default config;
