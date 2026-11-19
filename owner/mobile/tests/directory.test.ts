import { DirectoryError, verifyDirectoryRecord } from "../src/directory/verify";
import {
  directoryPayload,
  generateTestKeypair,
  signRecord,
  type TestKeypair,
} from "./helpers/directory";

function codeOf(run: () => unknown): string {
  try {
    run();
  } catch (error) {
    if (error instanceof DirectoryError) return error.code;
    throw error;
  }
  throw new Error("Expected verification to fail");
}

function keysFor(keypair: TestKeypair): Record<string, string> {
  return { k1: keypair.publicPem };
}

describe("signed school directory", () => {
  let keypair: TestKeypair;

  beforeAll(() => {
    keypair = generateTestKeypair();
  });

  it("accepts a valid signed record", () => {
    const record = signRecord(directoryPayload(), keypair.secretKey);
    const payload = verifyDirectoryRecord(record, { keys: keysFor(keypair) });
    expect(payload.instance_id).toBe(record.instance_id);
    expect(payload.api_base_url).toBe("https://demo.school.example");
    expect(payload.name).toBe("Demo Academy");
  });

  it("rejects a tampered outer field even with a valid signature", () => {
    const record = signRecord(directoryPayload(), keypair.secretKey);
    const tampered = { ...record, api_base_url: "https://attacker.example" };
    expect(codeOf(() => verifyDirectoryRecord(tampered, { keys: keysFor(keypair) }))).toBe(
      "FIELD_MISMATCH",
    );
  });

  it("rejects a tampered JWT payload", () => {
    const record = signRecord(directoryPayload(), keypair.secretKey);
    const [header, payload, signature] = record.signature.split(".");
    const decoded = JSON.parse(Buffer.from(payload!, "base64url").toString("utf8"));
    decoded.api_base_url = "https://attacker.example";
    const forgedBody = Buffer.from(JSON.stringify(decoded), "utf8").toString("base64url");
    const tampered = { ...record, signature: `${header}.${forgedBody}.${signature}` };
    const code = codeOf(() => verifyDirectoryRecord(tampered, { keys: keysFor(keypair) }));
    expect(["INVALID_SIGNATURE", "FIELD_MISMATCH"]).toContain(code);
  });

  it("rejects an unknown signing key id", () => {
    const record = signRecord(directoryPayload(), keypair.secretKey, "rotated");
    expect(codeOf(() => verifyDirectoryRecord(record, { keys: keysFor(keypair) }))).toBe("UNKNOWN_KID");
  });

  it("rejects an expired record", () => {
    const now = Math.floor(Date.now() / 1000);
    const record = signRecord(
      directoryPayload({ iat: now - 7200, exp: now - 60 }),
      keypair.secretKey,
    );
    expect(codeOf(() => verifyDirectoryRecord(record, { keys: keysFor(keypair) }))).toBe("EXPIRED");
  });

  it("rejects a record issued too far in the future", () => {
    const now = Math.floor(Date.now() / 1000);
    const record = signRecord(
      directoryPayload({ iat: now + 3600, exp: now + 7200 }),
      keypair.secretKey,
    );
    expect(codeOf(() => verifyDirectoryRecord(record, { keys: keysFor(keypair) }))).toBe(
      "ISSUED_IN_FUTURE",
    );
  });

  it("rejects a suspended school", () => {
    const record = signRecord(directoryPayload({ status: "suspended" }), keypair.secretKey);
    expect(codeOf(() => verifyDirectoryRecord(record, { keys: keysFor(keypair) }))).toBe(
      "SUSPENDED",
    );
  });

  it("rejects non-http api_base_url values", () => {
    const record = signRecord(
      directoryPayload({ api_base_url: "ftp://demo.school.example" }),
      keypair.secretKey,
    );
    expect(codeOf(() => verifyDirectoryRecord(record, { keys: keysFor(keypair) }))).toBe(
      "UNSUPPORTED_URL",
    );
  });

  it("rejects a malformed token", () => {
    const record = { ...signRecord(directoryPayload(), keypair.secretKey), signature: "not-a-jwt" };
    expect(codeOf(() => verifyDirectoryRecord(record, { keys: keysFor(keypair) }))).toBe(
      "MALFORMED_TOKEN",
    );
  });
});
