import { SessionError } from "../session/session";

/** Maps a failed attendance request to a translation key. */
export function attendanceErrorKey(caught: unknown, fallback: string): string {
  if (caught instanceof SessionError) {
    if (caught.code === "NETWORK_ERROR") return "attendance.error.network";
    if (caught.code === "PERMISSION_DENIED" || caught.code === "UNAUTHORIZED") {
      return "attendance.permission_denied";
    }
  }
  return fallback;
}

export function hasPermission(
  permissions: string[] | undefined,
  key: string,
): boolean {
  return Boolean(permissions?.includes("*") || permissions?.includes(key));
}

export function statusTone(
  status: string,
): "neutral" | "success" | "warning" | "danger" {
  if (status === "open" || status === "present") return "success";
  if (status === "submitted" || status === "late") return "warning";
  if (status === "absent") return "danger";
  return "neutral";
}
