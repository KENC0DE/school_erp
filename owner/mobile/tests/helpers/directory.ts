import * as ed from "@noble/ed25519";
import { sha512 } from "@noble/hashes/sha512";

import type { DirectoryPayload, DirectoryRecord } from "../../src/directory/types";

ed.utils.sha512Sync = (...messages: Uint8Array[]) =>
  sha512(ed.utils.concatBytes(...messages));

const ED25519_SPKI_PREFIX = Uint8Array.from([
  0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00,
]);

export interface TestKeypair {
  secretKey: Uint8Array;
  publicKey: Uint8Array;
  publicPem: string;
}

function toBase64(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64");
}

function wrapPem(body: string): string {
  const lines = body.match(/.{1,64}/g) ?? [];
  return `-----BEGIN PUBLIC KEY-----\n${lines.join("\n")}\n-----END PUBLIC KEY-----\n`;
}

export function publicKeyPem(publicKey: Uint8Array): string {
  const der = new Uint8Array(ED25519_SPKI_PREFIX.length + publicKey.length);
  der.set(ED25519_SPKI_PREFIX, 0);
  der.set(publicKey, ED25519_SPKI_PREFIX.length);
  return wrapPem(toBase64(der));
}

export function generateTestKeypair(): TestKeypair {
  const secretKey = ed.utils.randomPrivateKey();
  const publicKey = ed.sync.getPublicKey(secretKey);
  return { secretKey, publicKey, publicPem: publicKeyPem(publicKey) };
}

function base64UrlJson(value: unknown): string {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
}

export function signRecord(
  payload: Omit<DirectoryPayload, "kid"> & { kid?: string },
  secretKey: Uint8Array,
  kid = "k1",
): DirectoryRecord {
  const claims: DirectoryPayload = { ...payload, kid };
  const header = base64UrlJson({ alg: "EdDSA", typ: "JWT", kid });
  const body = base64UrlJson(claims);
  const signature = ed.sync.sign(new TextEncoder().encode(`${header}.${body}`), secretKey);
  return { ...claims, signature: `${header}.${body}.${Buffer.from(signature).toString("base64url")}` };
}

export function directoryPayload(
  overrides: Partial<Omit<DirectoryPayload, "kid">> = {},
): Omit<DirectoryPayload, "kid"> {
  const now = Math.floor(Date.now() / 1000);
  return {
    instance_id: "11111111-1111-4111-8111-111111111111",
    name: "Demo Academy",
    api_base_url: "https://demo.school.example",
    logo_url: null,
    status: "active",
    min_app_version: "0.1.0",
    iat: now,
    exp: now + 3600,
    ...overrides,
  };
}

export function useTestPublicKey(pem: string): void {
  process.env.EXPO_PUBLIC_CONTROLLER_DIRECTORY_PUBLIC_KEY = pem.replace(/\n/g, "\\n");
  process.env.EXPO_PUBLIC_CONTROLLER_DIRECTORY_KID = "k1";
}

export function clearTestPublicKey(): void {
  delete process.env.EXPO_PUBLIC_CONTROLLER_DIRECTORY_PUBLIC_KEY;
  delete process.env.EXPO_PUBLIC_CONTROLLER_DIRECTORY_KID;
}
