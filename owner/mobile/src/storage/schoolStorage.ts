
import {
  DIRECTORY_STATUS_SUSPENDED,
  profileFromPayload,
  type DirectoryRecord,
  type VerifiedProfile,
} from "../directory/types";
import { verifyDirectoryRecord } from "../directory/verify";
import { secureStorage } from "./secureStorage";

const PROFILE_INDEX_KEY = "erp.profile_index";
const ACTIVE_INSTANCE_KEY = "erp.active_instance";
const INSTANCE_ID_PATTERN = /^[A-Za-z0-9_-]+$/;
const CACHE_NAME_PATTERN = /^[A-Za-z0-9._-]+$/;

export type StorageErrorCode = "INVALID_INSTANCE_ID" | "PROFILE_NOT_VERIFIED";

export class StorageError extends Error {
  constructor(
    public readonly code: StorageErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "StorageError";
  }
}

export interface SchoolTokens {
  accessToken: string;
  refreshToken: string;
}

export function schoolStorageKeys(instanceId: string) {
  return {
    profile: `erp.school.${instanceId}.profile`,
    accessToken: `erp.${instanceId}.access_token`,
    refreshToken: `erp.${instanceId}.refresh_token`,
    cache: (name: string) => `erp.${instanceId}.cache.${name}`,
    preference: (name: string) => `erp.${instanceId}.pref.${name}`,
  };
}

function assertInstanceId(instanceId: string): void {
  if (!INSTANCE_ID_PATTERN.test(instanceId)) {
    throw new StorageError("INVALID_INSTANCE_ID", "School instance id is not safe to store");
  }
}

async function readJson<T>(key: string): Promise<T | null> {
  const raw = await secureStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

async function writeJson(key: string, value: unknown): Promise<void> {
  await secureStorage.setItem(key, JSON.stringify(value));
}

async function readIndex(): Promise<string[]> {
  const value = await readJson<unknown>(PROFILE_INDEX_KEY);
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

/**
 * A profile is only returned when its stored signed record still verifies
 * against the embedded controller key. The denormalised fields are rebuilt from
 * the signed payload so a tampered profile cannot change the server address.
 */
export async function getVerifiedProfile(instanceId: string): Promise<VerifiedProfile | null> {
  assertInstanceId(instanceId);
  const stored = await readJson<{ record?: unknown }>(schoolStorageKeys(instanceId).profile);
  if (!stored?.record) return null;
  let payload;
  try {
    payload = verifyDirectoryRecord(stored.record, { requireFresh: false });
  } catch {
    return null;
  }
  if (payload.instance_id !== instanceId || payload.status === DIRECTORY_STATUS_SUSPENDED) {
    return null;
  }
  const profile = profileFromPayload(payload, stored.record as DirectoryRecord);
  const storedVerifiedAt = (stored as { verifiedAt?: unknown }).verifiedAt;
  if (typeof storedVerifiedAt === "string") profile.verifiedAt = storedVerifiedAt;
  return profile;
}

export async function listProfiles(): Promise<VerifiedProfile[]> {
  const ids = await readIndex();
  const profiles = await Promise.all(ids.map((id) => getVerifiedProfile(id)));
  return profiles.filter((profile): profile is VerifiedProfile => profile !== null);
}

/** Verifies a fresh directory record before persisting it as a trusted school profile. */
export async function storeVerifiedProfile(record: unknown): Promise<VerifiedProfile> {
  const payload = verifyDirectoryRecord(record);
  assertInstanceId(payload.instance_id);
  const profile = profileFromPayload(payload, record as DirectoryRecord);
  const keys = schoolStorageKeys(profile.instanceId);
  await writeJson(keys.profile, profile);
  const index = await readIndex();
  if (!index.includes(profile.instanceId)) {
    await writeJson(PROFILE_INDEX_KEY, [...index, profile.instanceId]);
  }
  return profile;
}

export async function removeProfile(instanceId: string): Promise<void> {
  assertInstanceId(instanceId);
  const keys = schoolStorageKeys(instanceId);
  await secureStorage.deleteItem(keys.profile);
  await secureStorage.deleteItem(keys.accessToken);
  await secureStorage.deleteItem(keys.refreshToken);
  const index = await readIndex();
  await writeJson(
    PROFILE_INDEX_KEY,
    index.filter((id) => id !== instanceId),
  );
  if ((await secureStorage.getItem(ACTIVE_INSTANCE_KEY)) === instanceId) {
    await secureStorage.deleteItem(ACTIVE_INSTANCE_KEY);
  }
}

export async function setActiveInstance(instanceId: string): Promise<void> {
  assertInstanceId(instanceId);
  if (!(await getVerifiedProfile(instanceId))) {
    throw new StorageError("PROFILE_NOT_VERIFIED", "School is not a verified profile");
  }
  await secureStorage.setItem(ACTIVE_INSTANCE_KEY, instanceId);
}

export async function getActiveInstanceId(): Promise<string | null> {
  const instanceId = await secureStorage.getItem(ACTIVE_INSTANCE_KEY);
  if (!instanceId) return null;
  return (await getVerifiedProfile(instanceId)) ? instanceId : null;
}

/** Returns only the signed api_base_url of a verified profile. */
export async function getVerifiedBaseUrl(instanceId: string): Promise<string> {
  const profile = await getVerifiedProfile(instanceId);
  if (!profile) {
    throw new StorageError("PROFILE_NOT_VERIFIED", "School is not a verified profile");
  }
  return profile.apiBaseUrl.replace(/\/$/, "");
}

export interface SchoolStorage {
  instanceId: string;
  getProfile: () => Promise<VerifiedProfile>;
  getAccessToken: () => Promise<string | null>;
  getRefreshToken: () => Promise<string | null>;
  setTokens: (tokens: SchoolTokens) => Promise<void>;
  clearTokens: () => Promise<void>;
  getCache: <T>(name: string) => Promise<T | null>;
  setCache: (name: string, value: unknown) => Promise<void>;
  getPreference: (name: string) => Promise<string | null>;
  setPreference: (name: string, value: string) => Promise<void>;
}

/**
 * Namespaced facade. Every read and write checks that the school has a verified
 * profile first, so a caller can never point storage at an unverified server.
 */
export function forSchool(instanceId: string): SchoolStorage {
  assertInstanceId(instanceId);
  const keys = schoolStorageKeys(instanceId);

  async function requireProfile(): Promise<VerifiedProfile> {
    const profile = await getVerifiedProfile(instanceId);
    if (!profile) {
      throw new StorageError("PROFILE_NOT_VERIFIED", "School is not a verified profile");
    }
    return profile;
  }

  function assertCacheName(name: string): void {
    if (!CACHE_NAME_PATTERN.test(name)) {
      throw new StorageError("INVALID_INSTANCE_ID", "Cache name is not safe to store");
    }
  }

  return {
    instanceId,
    getProfile: requireProfile,
    async getAccessToken() {
      await requireProfile();
      return secureStorage.getItem(keys.accessToken);
    },
    async getRefreshToken() {
      await requireProfile();
      return secureStorage.getItem(keys.refreshToken);
    },
    async setTokens(tokens) {
      await requireProfile();
      await secureStorage.setItem(keys.accessToken, tokens.accessToken);
      await secureStorage.setItem(keys.refreshToken, tokens.refreshToken);
    },
    async clearTokens() {
      await requireProfile();
      await secureStorage.deleteItem(keys.accessToken);
      await secureStorage.deleteItem(keys.refreshToken);
    },
    async getCache<T>(name: string) {
      await requireProfile();
      assertCacheName(name);
      return readJson<T>(keys.cache(name));
    },
    async setCache(name, value) {
      await requireProfile();
      assertCacheName(name);
      await writeJson(keys.cache(name), value);
    },
    async getPreference(name: string) {
      await requireProfile();
      assertCacheName(name);
      return secureStorage.getItem(keys.preference(name));
    },
    async setPreference(name, value) {
      await requireProfile();
      assertCacheName(name);
      await secureStorage.setItem(keys.preference(name), value);
    },
  };
}
