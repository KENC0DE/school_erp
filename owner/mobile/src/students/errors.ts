import { SessionError } from "../session/session";

/**
 * Maps a failed student request to a translation key. Network and permission
 * failures get specific messages; everything else falls back to the caller's
 * screen-level error key.
 */
export function studentErrorKey(caught: unknown, fallback: string): string {
  if (caught instanceof SessionError) {
    if (caught.code === "NETWORK_ERROR") return "students.error.network";
    if (caught.code === "PERMISSION_DENIED" || caught.code === "UNAUTHORIZED") {
      return "students.permission_denied";
    }
  }
  return fallback;
}
