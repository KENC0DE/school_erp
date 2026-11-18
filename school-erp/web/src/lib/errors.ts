import { ApiRequestError } from "@erp/api-client";

/**
 * The request id the API puts on every error response. Screens show it next to
 * a retry action so support can find the exact request (UI checklist §3).
 */
export function requestIdOf(error: unknown): string | undefined {
  return error instanceof ApiRequestError ? error.requestId : undefined;
}
