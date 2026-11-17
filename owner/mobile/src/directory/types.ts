export interface DirectoryPayload {
  instance_id: string;
  name: string;
  api_base_url: string;
  logo_url: string | null;
  status: string;
  min_app_version: string;
  iat: number;
  exp: number;
  kid: string;
}

export interface DirectoryRecord extends DirectoryPayload {
  signature: string;
}

export interface VerifiedProfile {
  instanceId: string;
  name: string;
  apiBaseUrl: string;
  logoUrl: string | null;
  status: string;
  minAppVersion: string;
  kid: string;
  verifiedAt: string;
  record: DirectoryRecord;
}

export const DIRECTORY_STATUS_SUSPENDED = "suspended";

export function profileFromPayload(payload: DirectoryPayload, record: DirectoryRecord): VerifiedProfile {
  return {
    instanceId: payload.instance_id,
    name: payload.name,
    apiBaseUrl: payload.api_base_url.replace(/\/$/, ""),
    logoUrl: payload.logo_url,
    status: payload.status,
    minAppVersion: payload.min_app_version,
    kid: payload.kid,
    verifiedAt: new Date().toISOString(),
    record,
  };
}
