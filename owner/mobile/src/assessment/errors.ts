import { SessionError } from "../session/session";

/** Maps a failed assessment request to a translation key. */
export function assessmentErrorKey(caught: unknown, fallback: string): string {
  if (caught instanceof SessionError) {
    if (caught.code === "NETWORK_ERROR") return "assessment.error.network";
    if (caught.code === "PERMISSION_DENIED" || caught.code === "UNAUTHORIZED") {
      return "assessment.mobile.no_permission";
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

/** A stale `row_version` or another version conflict comes back as HTTP 409. */
export function isConflict(caught: unknown): boolean {
  return (
    caught instanceof SessionError &&
    (caught.status === 409 ||
      caught.code === "CONFLICT" ||
      caught.code === "VERSION_CONFLICT")
  );
}

export function syncTone(
  state: string,
): "neutral" | "success" | "warning" | "danger" {
  if (state === "saved") return "success";
  if (state === "pending" || state === "saving") return "warning";
  if (state === "error" || state === "conflict") return "danger";
  return "neutral";
}
