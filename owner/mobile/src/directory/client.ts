import { controllerBaseUrl } from "../config/env";
import { normaliseSchoolCode } from "./qr";
import { DIRECTORY_STATUS_SUSPENDED, profileFromPayload, type DirectoryRecord, type VerifiedProfile } from "./types";
import { DirectoryError, verifyDirectoryRecord } from "./verify";

export interface ResolveSchoolOptions {
  fetcher?: typeof fetch;
  controllerUrl?: string;
}

/**
 * Resolves a school code through the controller and refuses to return a profile
 * unless the signed response verifies against the embedded directory key set.
 */
export async function resolveSchoolCode(
  rawCode: string,
  options: ResolveSchoolOptions = {},
): Promise<VerifiedProfile> {
  const code = normaliseSchoolCode(rawCode);
  if (!code) {
    throw new DirectoryError("INVALID_CODE", "School code is not valid");
  }
  const fetcher = options.fetcher ?? fetch;
  const baseUrl = (options.controllerUrl ?? controllerBaseUrl()).replace(/\/$/, "");
  let response: Response;
  try {
    response = await fetcher(
      `${baseUrl}/controller/v1/directory/resolve?code=${encodeURIComponent(code)}`,
      { headers: { Accept: "application/json" } },
    );
  } catch {
    throw new DirectoryError("NETWORK_ERROR", "Cannot reach the controller");
  }
  if (response.status === 404) {
    throw new DirectoryError("NOT_FOUND", "School not found");
  }
  if (response.status === 429) {
    throw new DirectoryError("RATE_LIMITED", "Too many school lookups");
  }
  if (!response.ok) {
    throw new DirectoryError("INVALID_RESPONSE", "Controller returned an unexpected response");
  }
  let record: unknown;
  try {
    record = await response.json();
  } catch {
    throw new DirectoryError("INVALID_RESPONSE", "Controller response is not JSON");
  }
  const payload = verifyDirectoryRecord(record);
  if (payload.status === DIRECTORY_STATUS_SUSPENDED) {
    throw new DirectoryError("SUSPENDED", "School is suspended", payload);
  }
  return profileFromPayload(payload, record as DirectoryRecord);
}
