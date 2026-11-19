import * as SecureStore from "expo-secure-store";

import { login, refreshSession, type SessionDeps } from "../src/session/session";
import { forSchool, storeVerifiedProfile } from "../src/storage/schoolStorage";
import {
  clearTestPublicKey,
  directoryPayload,
  generateTestKeypair,
  signRecord,
  useTestPublicKey,
  type TestKeypair,
} from "./helpers/directory";

const secureStoreMock = SecureStore as unknown as { __reset: () => void };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const loginBody = {
  tokens: { access_token: "access-1", refresh_token: "refresh-1", token_type: "bearer", expires_in: 900 },
  user: {
    id: "user-1",
    email: "user@demo.school",
    display_name: "Demo User",
    locale: "en",
    roles: ["teacher"],
    permissions: ["sample.notes.view"],
  },
};

describe("school session", () => {
  let keypair: TestKeypair;
  const originalFetch = global.fetch;

  beforeAll(() => {
    keypair = generateTestKeypair();
    useTestPublicKey(keypair.publicPem);
    global.fetch = originalFetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
    clearTestPublicKey();
  });

  beforeEach(async () => {
    secureStoreMock.__reset();
    const record = signRecord(
      directoryPayload({
        instance_id: "school-alpha",
        api_base_url: "https://alpha.school.example",
      }),
      keypair.secretKey,
    );
    await storeVerifiedProfile(record);
  });

  it("logs in against the stored verified api_base_url, ignoring a caller supplied URL", async () => {
    const fetcher = jest.fn().mockResolvedValue(jsonResponse(loginBody));
    const attackerUrl = "https://attacker.example";
    const deps = { fetcher, baseUrl: attackerUrl } as unknown as SessionDeps;

    const result = await login("school-alpha", " User@Demo.School ", "DevPass#2026", deps);

    expect(result.user.id).toBe("user-1");
    expect(fetcher).toHaveBeenCalledTimes(1);
    const [url, init] = fetcher.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://alpha.school.example/api/v1/auth/login");
    expect(url).not.toContain(attackerUrl);
    expect(JSON.parse(String(init.body))).toEqual({
      email: "user@demo.school",
      password: "DevPass#2026",
    });
    expect(await forSchool("school-alpha").getAccessToken()).toBe("access-1");
    expect(await forSchool("school-alpha").getRefreshToken()).toBe("refresh-1");
  });

  it("refuses a school address that was never verified", async () => {
    const fetcher = jest.fn();
    const deps = {
      fetcher,
      baseUrl: "https://attacker.example",
      instanceId: "school-unverified",
    } as unknown as SessionDeps;

    await expect(login("school-unverified", "user@demo.school", "DevPass#2026", deps)).rejects.toMatchObject({
      code: "PROFILE_NOT_VERIFIED",
    });
    expect(fetcher).not.toHaveBeenCalled();
    await expect(forSchool("school-unverified").getAccessToken()).rejects.toMatchObject({
      code: "PROFILE_NOT_VERIFIED",
    });
  });

  it("rotates tokens through the verified school server", async () => {
    await forSchool("school-alpha").setTokens({ accessToken: "old-access", refreshToken: "old-refresh" });
    const fetcher = jest.fn().mockResolvedValue(
      jsonResponse({ access_token: "new-access", refresh_token: "new-refresh", expires_in: 900 }),
    );

    const tokens = await refreshSession("school-alpha", { fetcher });

    expect(tokens.access_token).toBe("new-access");
    const [url, init] = fetcher.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://alpha.school.example/api/v1/auth/refresh");
    expect(JSON.parse(String(init.body))).toEqual({ refresh_token: "old-refresh" });
    expect(await forSchool("school-alpha").getAccessToken()).toBe("new-access");
    expect(await forSchool("school-alpha").getRefreshToken()).toBe("new-refresh");
  });
});
