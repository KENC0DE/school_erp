import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

/**
 * Secure storage adapter. Native builds use expo-secure-store (Keychain /
 * Keystore). Expo Go's web target has no keychain, so the design-review build
 * falls back to localStorage; tokens are still namespaced per school there.
 * A web production build is not a supported deployment target for the app.
 */
const isWeb = Platform.OS === "web";

function webStorage(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export const secureStorage = {
  async getItem(key: string): Promise<string | null> {
    if (isWeb) return webStorage()?.getItem(key) ?? null;
    return SecureStore.getItemAsync(key);
  },

  async setItem(key: string, value: string): Promise<void> {
    if (isWeb) {
      webStorage()?.setItem(key, value);
      return;
    }
    await SecureStore.setItemAsync(key, value);
  },

  async deleteItem(key: string): Promise<void> {
    if (isWeb) {
      webStorage()?.removeItem(key);
      return;
    }
    await SecureStore.deleteItemAsync(key);
  },
};
