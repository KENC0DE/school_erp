export function controllerBaseUrl(): string {
  const configured = process.env.EXPO_PUBLIC_CONTROLLER_URL;
  return (configured && configured.trim() !== "" ? configured : "http://localhost:8100").replace(
    /\/$/,
    "",
  );
}
