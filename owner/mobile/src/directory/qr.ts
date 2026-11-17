const QR_PATTERN = /^erpapp:\/\/school\/([A-Za-z0-9_-]{2,32})\/?$/i;
export const SCHOOL_CODE_PATTERN = /^[A-Z0-9_-]{2,32}$/;

export function normaliseSchoolCode(value: string): string | null {
  const candidate = value.trim().toUpperCase();
  return SCHOOL_CODE_PATTERN.test(candidate) ? candidate : null;
}

/**
 * Parses the controller's `erpapp://school/<code>` QR payload. Returns null for
 * anything else so callers can distinguish "not our QR code" from a network error.
 */
export function parseSchoolQrPayload(payload: string): string | null {
  const trimmed = payload.trim();
  const match = QR_PATTERN.exec(trimmed);
  if (!match?.[1]) return null;
  return normaliseSchoolCode(match[1]);
}
