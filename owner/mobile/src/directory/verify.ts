import * as ed from "@noble/ed25519";
import { sha512 } from "@noble/hashes/sha512";

import { directoryKeySet } from "../config/keys";
import {
  DIRECTORY_STATUS_SUSPENDED,
  type DirectoryPayload,
  type DirectoryRecord,
} from "./types";

ed.utils.sha512Sync = (...messages: Uint8Array[]) =>
  sha512(ed.utils.concatBytes(...messages));

const BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const ED25519_SPKI_PREFIX = [0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00];

export type DirectoryErrorCode =
  | "INVALID_CODE"
  | "NOT_FOUND"
  | "RATE_LIMITED"
  | "NETWORK_ERROR"
  | "INVALID_RESPONSE"
  | "MALFORMED_RECORD"
  | "MALFORMED_TOKEN"
  | "UNSUPPORTED_ALGORITHM"
  | "UNKNOWN_KID"
  | "BAD_KEY"
  | "INVALID_SIGNATURE"
  | "FIELD_MISMATCH"
  | "EXPIRED"
  | "ISSUED_IN_FUTURE"
  | "UNSUPPORTED_URL"
  | "SUSPENDED";

export class DirectoryError extends Error {
  constructor(
    public readonly code: DirectoryErrorCode,
    message: string,
    public readonly payload?: DirectoryPayload,
  ) {
    super(message);
    this.name = "DirectoryError";
  }
}

function decodeBase64(input: string, urlSafe: boolean): Uint8Array {
  const normalised = urlSafe ? input.replace(/-/g, "+").replace(/_/g, "/") : input;
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(normalised)) {
    throw new Error("Invalid base64");
  }
  const clean = normalised.replace(/=+$/, "");
  if (clean.length % 4 === 1) throw new Error("Invalid base64 length");
  const bytes: number[] = [];
  for (let index = 0; index < clean.length; index += 4) {
    const chunk = clean.slice(index, index + 4);
    const values = Array.from(chunk, (character) => BASE64_ALPHABET.indexOf(character));
    if (values.some((value) => value < 0)) throw new Error("Invalid base64 character");
    const [a = 0, b = 0, c = 0, d = 0] = values;
    bytes.push((a << 2) | (b >> 4));
    if (chunk.length > 2) bytes.push(((b & 15) << 4) | (c >> 2));
    if (chunk.length > 3) bytes.push(((c & 3) << 6) | d);
  }
  return Uint8Array.from(bytes);
}

function decodeUtf8(bytes: Uint8Array): string {
  let output = "";
  let index = 0;
  while (index < bytes.length) {
    const first = bytes[index]!;
    if (first < 0x80) {
      output += String.fromCharCode(first);
      index += 1;
    } else if ((first & 0xe0) === 0xc0) {
      const second = bytes[index + 1]!;
      output += String.fromCharCode(((first & 0x1f) << 6) | (second & 0x3f));
      index += 2;
    } else if ((first & 0xf0) === 0xe0) {
      const second = bytes[index + 1]!;
      const third = bytes[index + 2]!;
      output += String.fromCharCode(
        ((first & 0x0f) << 12) | ((second & 0x3f) << 6) | (third & 0x3f),
      );
      index += 3;
    } else if ((first & 0xf8) === 0xf0) {
      const second = bytes[index + 1]!;
      const third = bytes[index + 2]!;
      const fourth = bytes[index + 3]!;
      const codePoint =
        ((first & 0x07) << 18) |
        ((second & 0x3f) << 12) |
        ((third & 0x3f) << 6) |
        (fourth & 0x3f);
      output += String.fromCodePoint(codePoint);
      index += 4;
    } else {
      throw new Error("Invalid UTF-8");
    }
  }
  return output;
}

function publicKeyFromPem(pem: string): Uint8Array {
  const match = pem.match(/-----BEGIN PUBLIC KEY-----([\s\S]*?)-----END PUBLIC KEY-----/);
  if (!match?.[1]) throw new DirectoryError("BAD_KEY", "Directory public key is not PEM");
  let der: Uint8Array;
  try {
    der = decodeBase64(match[1].replace(/\s+/g, ""), false);
  } catch {
    throw new DirectoryError("BAD_KEY", "Directory public key is not valid base64");
  }
  const prefixMatches = ED25519_SPKI_PREFIX.every((byte, index) => der[index] === byte);
  if (der.length !== 44 || !prefixMatches) {
    throw new DirectoryError("BAD_KEY", "Directory public key is not an Ed25519 SPKI key");
  }
  return der.slice(ED25519_SPKI_PREFIX.length);
}

function decodeJwtPart(part: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(decodeUtf8(decodeBase64(part, true))) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("JWT part is not an object");
    }
    return parsed as Record<string, unknown>;
  } catch {
    throw new DirectoryError("MALFORMED_TOKEN", "Directory token is malformed");
  }
}

const COMPARED_FIELDS: Array<keyof DirectoryPayload> = [
  "instance_id",
  "name",
  "api_base_url",
  "logo_url",
  "status",
  "min_app_version",
  "iat",
  "exp",
  "kid",
];

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function validateOuterRecord(record: unknown): DirectoryRecord {
  if (!record || typeof record !== "object" || Array.isArray(record)) {
    throw new DirectoryError("MALFORMED_RECORD", "Directory response is not an object");
  }
  const candidate = record as Record<string, unknown>;
  if (typeof candidate.signature !== "string" || candidate.signature === "") {
    throw new DirectoryError("MALFORMED_RECORD", "Directory response has no signature");
  }
  for (const field of COMPARED_FIELDS) {
    if (field === "logo_url") {
      if (candidate[field] !== null && typeof candidate[field] !== "string") {
        throw new DirectoryError("MALFORMED_RECORD", "Directory response has an invalid logo_url");
      }
      continue;
    }
    if (field === "iat" || field === "exp") {
      if (!isFiniteNumber(candidate[field])) {
        throw new DirectoryError("MALFORMED_RECORD", `Directory response has an invalid ${field}`);
      }
      continue;
    }
    if (typeof candidate[field] !== "string" || candidate[field] === "") {
      throw new DirectoryError("MALFORMED_RECORD", `Directory response has an invalid ${field}`);
    }
  }
  return candidate as unknown as DirectoryRecord;
}

function validateApiBaseUrl(value: string): void {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new DirectoryError("UNSUPPORTED_URL", "School API address is not a URL");
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new DirectoryError("UNSUPPORTED_URL", "School API address must use http or https");
  }
  if (url.username || url.password) {
    throw new DirectoryError("UNSUPPORTED_URL", "School API address must not contain credentials");
  }
}

export interface VerifyOptions {
  keys?: Record<string, string>;
  nowSeconds?: number;
  requireFresh?: boolean;
  clockSkewSeconds?: number;
}

/**
 * Verifies the controller's EdDSA-signed directory record end to end:
 * signature, key id, freshness, URL scheme, suspension state and every outer
 * field against the signed payload. Returns only the signed payload.
 */
export function verifyDirectoryRecord(
  record: unknown,
  options: VerifyOptions = {},
): DirectoryPayload {
  const outer = validateOuterRecord(record);
  const parts = outer.signature.split(".");
  if (parts.length !== 3 || parts.some((part) => part === "")) {
    throw new DirectoryError("MALFORMED_TOKEN", "Directory signature is not a JWT");
  }
  const [encodedHeader, encodedPayload, encodedSignature] = parts as [string, string, string];
  const header = decodeJwtPart(encodedHeader);
  if (header.alg !== "EdDSA") {
    throw new DirectoryError("UNSUPPORTED_ALGORITHM", "Directory token is not EdDSA");
  }
  if (typeof header.kid !== "string" || header.kid === "") {
    throw new DirectoryError("MALFORMED_TOKEN", "Directory token has no key id");
  }
  const keys = options.keys ?? directoryKeySet();
  const pem = keys[header.kid];
  if (!pem) {
    throw new DirectoryError("UNKNOWN_KID", `Unknown directory key ${header.kid}`);
  }
  const payload = decodeJwtPart(encodedPayload) as unknown as DirectoryPayload;
  let signature: Uint8Array;
  try {
    signature = decodeBase64(encodedSignature, true);
  } catch {
    throw new DirectoryError("MALFORMED_TOKEN", "Directory signature is malformed");
  }
  if (signature.length !== 64) {
    throw new DirectoryError("MALFORMED_TOKEN", "Directory signature has the wrong length");
  }
  const signingInput = new TextEncoder().encode(`${encodedHeader}.${encodedPayload}`);
  let valid = false;
  try {
    valid = ed.sync.verify(signature, signingInput, publicKeyFromPem(pem));
  } catch (error) {
    if (error instanceof DirectoryError) throw error;
  }
  if (!valid) {
    throw new DirectoryError("INVALID_SIGNATURE", "Directory signature is invalid");
  }
  if (payload.kid !== header.kid) {
    throw new DirectoryError("FIELD_MISMATCH", "Directory key id does not match the token");
  }
  for (const field of COMPARED_FIELDS) {
    if (payload[field] !== outer[field]) {
      throw new DirectoryError("FIELD_MISMATCH", `Directory ${field} was altered`);
    }
  }
  if (payload.iat > payload.exp) {
    throw new DirectoryError("MALFORMED_TOKEN", "Directory token is not time-ordered");
  }
  const nowSeconds = options.nowSeconds ?? Math.floor(Date.now() / 1000);
  if (options.requireFresh !== false) {
    if (payload.exp <= nowSeconds) {
      throw new DirectoryError("EXPIRED", "Directory record has expired", payload);
    }
    const skew = options.clockSkewSeconds ?? 300;
    if (payload.iat > nowSeconds + skew) {
      throw new DirectoryError("ISSUED_IN_FUTURE", "Directory record is from the future", payload);
    }
  }
  validateApiBaseUrl(payload.api_base_url);
  if (payload.status === DIRECTORY_STATUS_SUSPENDED) {
    throw new DirectoryError("SUSPENDED", "School is suspended", payload);
  }
  return payload;
}
