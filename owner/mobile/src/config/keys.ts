/**
 * Trust anchor for the controller's signed school directory.
 *
 * The default key below is a DEV-ONLY keypair generated for this repository.
 * Start the controller with the matching DIRECTORY_PRIVATE_KEY before its first
 * boot, or reset its signing-key table once, otherwise the controller generates
 * a different key and app resolution fails. Production builds must replace it
 * with EXPO_PUBLIC_CONTROLLER_DIRECTORY_PUBLIC_KEY (and set
 * EXPO_PUBLIC_CONTROLLER_DIRECTORY_KID when the controller rotates keys).
 * Only public keys belong here; the matching private key stays in the controller's
 * environment (DIRECTORY_PRIVATE_KEY).
 */
export const DEFAULT_DIRECTORY_KID = "k1";

export const DEV_ONLY_DIRECTORY_PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA1SO8275AuBMg2ZZIDF4FRx7t+7actHDQ2CXhLr8Z7Bo=
-----END PUBLIC KEY-----
`;

function normalisePem(value: string): string {
  return value.includes("\\n") ? value.replace(/\\n/g, "\n") : value;
}

export function directoryKeySet(): Record<string, string> {
  const kid = process.env.EXPO_PUBLIC_CONTROLLER_DIRECTORY_KID || DEFAULT_DIRECTORY_KID;
  const keys: Record<string, string> = {
    [DEFAULT_DIRECTORY_KID]: DEV_ONLY_DIRECTORY_PUBLIC_KEY,
  };
  const configured = process.env.EXPO_PUBLIC_CONTROLLER_DIRECTORY_PUBLIC_KEY;
  if (configured && configured.trim() !== "") {
    keys[kid] = normalisePem(configured);
  }
  return keys;
}
