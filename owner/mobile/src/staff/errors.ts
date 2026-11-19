import { SessionError } from "../session/session";

/** Maps a failed staff request to a translation key. */
export function staffErrorKey(caught: unknown, fallback: string): string {
  if (caught instanceof SessionError) {
    if (caught.code === "NETWORK_ERROR") return "staff.error.network";
    if (caught.code === "PERMISSION_DENIED" || caught.code === "UNAUTHORIZED") {
      return "staff.permission_denied";
    }
  }
  return fallback;
}
