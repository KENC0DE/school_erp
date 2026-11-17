import * as SecureStore from "expo-secure-store";

import {
  forSchool,
  getVerifiedBaseUrl,
  getVerifiedProfile,
  listProfiles,
  storeVerifiedProfile,
} from "../src/storage/schoolStorage";
import { verifyDirectoryRecord } from "../src/directory/verify";
import {
  clearTestPublicKey,
  directoryPayload,
  generateTestKeypair,
  signRecord,
  useTestPublicKey,
  type TestKeypair,
} from "./helpers/directory";

const secureStoreMock = SecureStore as unknown as {
  __reset: () => void;
  __setRaw: (key: string, value: string) => void;
  __entries: () => Array<[string, string]>;
};

describe("per-school secure storage", () => {
  let keypair: TestKeypair;

  beforeAll(() => {
    keypair = generateTestKeypair();
    useTestPublicKey(keypair.publicPem);
  });

  afterAll(() => {
    clearTestPublicKey();
  });

  beforeEach(() => {
    secureStoreMock.__reset();
  });

  async function storeTwoSchools() {
    const alpha = signRecord(
      directoryPayload({
        instance_id: "school-alpha",
        name: "Alpha Academy",
        api_base_url: "https://alpha.school.example/",
      }),
      keypair.secretKey,
    );
    const beta = signRecord(
      directoryPayload({
        instance_id: "school-beta",
        name: "Beta Academy",
        api_base_url: "https://beta.school.example",
      }),
      keypair.secretKey,
    );
    await storeVerifiedProfile(alpha);
    await storeVerifiedProfile(beta);
    return { alpha, beta };
  }

  it("keeps tokens and caches in separate namespaces for two schools", async () => {
    await storeTwoSchools();

    await forSchool("school-alpha").setTokens({ accessToken: "alpha-access", refreshToken: "alpha-refresh" });
    await forSchool("school-beta").setTokens({ accessToken: "beta-access", refreshToken: "beta-refresh" });
    await forSchool("school-alpha").setCache("navigation", { items: [{ key: "alpha" }] });
    await forSchool("school-beta").setCache("navigation", { items: [{ key: "beta" }] });

    expect(await forSchool("school-alpha").getAccessToken()).toBe("alpha-access");
    expect(await forSchool("school-beta").getAccessToken()).toBe("beta-access");
    expect(await forSchool("school-alpha").getRefreshToken()).toBe("alpha-refresh");
    expect(await forSchool("school-beta").getRefreshToken()).toBe("beta-refresh");
    expect(await forSchool("school-alpha").getCache("navigation")).toEqual({ items: [{ key: "alpha" }] });
    expect(await forSchool("school-beta").getCache("navigation")).toEqual({ items: [{ key: "beta" }] });

    const keys = secureStoreMock.__entries().map(([key]) => key);
    expect(keys).toContain("erp.school-alpha.access_token");
    expect(keys).toContain("erp.school-beta.access_token");
    expect(keys).toContain("erp.school-alpha.refresh_token");
    expect(keys).toContain("erp.school-beta.refresh_token");
    expect(keys).toContain("erp.school-alpha.cache.navigation");
    expect(keys).toContain("erp.school-beta.cache.navigation");
    expect(keys).not.toContain("erp.access_token");
  });

  it("returns the verified api_base_url for each school", async () => {
    await storeTwoSchools();
    expect(await getVerifiedBaseUrl("school-alpha")).toBe("https://alpha.school.example");
    expect(await getVerifiedBaseUrl("school-beta")).toBe("https://beta.school.example");
    expect((await listProfiles()).map((profile) => profile.instanceId).sort()).toEqual([
      "school-alpha",
      "school-beta",
    ]);
  });

  it("refuses token and cache access for a school without a verified profile", async () => {
    await expect(forSchool("never-verified").getAccessToken()).rejects.toMatchObject({
      code: "PROFILE_NOT_VERIFIED",
    });
    await expect(
      forSchool("never-verified").setTokens({ accessToken: "x", refreshToken: "y" }),
    ).rejects.toMatchObject({ code: "PROFILE_NOT_VERIFIED" });
    await expect(forSchool("never-verified").setCache("navigation", {})).rejects.toMatchObject({
      code: "PROFILE_NOT_VERIFIED",
    });
    await expect(getVerifiedBaseUrl("never-verified")).rejects.toMatchObject({
      code: "PROFILE_NOT_VERIFIED",
    });
  });

  it("ignores denormalised profile fields and trusts only the signed record", async () => {
    await storeTwoSchools();
    const profile = await getVerifiedProfile("school-alpha");
    secureStoreMock.__setRaw(
      "erp.school.school-alpha.profile",
      JSON.stringify({ ...profile, apiBaseUrl: "https://attacker.example" }),
    );
    expect(await getVerifiedBaseUrl("school-alpha")).toBe("https://alpha.school.example");
  });

  it("rejects a stored profile whose signed record was tampered with", async () => {
    await storeTwoSchools();
    const profile = await getVerifiedProfile("school-alpha");
    const record = { ...profile!.record, api_base_url: "https://attacker.example" };
    secureStoreMock.__setRaw(
      "erp.school.school-alpha.profile",
      JSON.stringify({ ...profile, record }),
    );
    expect(() => verifyDirectoryRecord(record, { requireFresh: false })).toThrow();
    await expect(getVerifiedBaseUrl("school-alpha")).rejects.toMatchObject({
      code: "PROFILE_NOT_VERIFIED",
    });
  });
});
