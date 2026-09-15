import nacl from 'tweetnacl';
import { sha256 } from 'js-sha256';

export const GENESIS_HASH = '0'.repeat(64);

export function hexToBytes(hex: string): Uint8Array {
  const clean = hex.trim().replace(/^0x/, '');
  if (clean.length % 2 !== 0) {
    throw new Error(`Invalid hex length: ${clean.length}`);
  }
  const bytes = new Uint8Array(clean.length / 2);
  for (let i = 0; i < clean.length; i += 2) {
    bytes[i / 2] = parseInt(clean.substring(i, i + 2), 16);
  }
  return bytes;
}

export function bytesToHex(bytes: Uint8Array): string {
  let hex = '';
  for (let i = 0; i < bytes.length; i++) {
    hex += bytes[i].toString(16).padStart(2, '0');
  }
  return hex;
}

function formatValue(key: string, val: any): string {
  if (typeof val === 'number') {
    if (key === 'amount') {
      return Number.isInteger(val) ? val.toFixed(1) : val.toString();
    }
    return val.toString();
  }
  return JSON.stringify(val);
}

/**
 * Deterministic JSON serialization matching Python's sort_keys=True, separators=(',', ':').
 */
export function serializeForHashing(obj: any): string {
  if (obj === null || typeof obj !== 'object') {
    return JSON.stringify(obj);
  }
  if (Array.isArray(obj)) {
    return '[' + obj.map(serializeForHashing).join(',') + ']';
  }
  const keys = Object.keys(obj).sort();
  const pairs: string[] = [];
  for (const k of keys) {
    if (obj[k] !== undefined && obj[k] !== null) {
      const valStr =
        typeof obj[k] === 'object' ? serializeForHashing(obj[k]) : formatValue(k, obj[k]);
      pairs.push(JSON.stringify(k) + ':' + valStr);
    }
  }
  return '{' + pairs.join(',') + '}';
}

/**
 * Compute SHA-256(previous_hash + payload_bytes + signatures_bytes).
 */
export function generateEventHash(
  previousHash: string,
  payloadBytes: Uint8Array,
  signaturesBytes: Uint8Array
): string {
  const hasher = sha256.create();
  hasher.update(Buffer.from(previousHash, 'utf-8'));
  hasher.update(payloadBytes);
  hasher.update(signaturesBytes);
  return hasher.hex();
}

/**
 * Generate an Ed25519 keypair for Teller or Customer.
 */
export function generateKeyPair(): { privateKeyHex: string; publicKeyHex: string } {
  const keyPair = nacl.sign.keyPair();
  // tweetnacl secretKey is 64 bytes (32 bytes private seed + 32 bytes public key)
  // Python nacl uses 32 bytes private seed
  const privateSeed = keyPair.secretKey.subarray(0, 32);
  return {
    privateKeyHex: bytesToHex(privateSeed),
    publicKeyHex: bytesToHex(keyPair.publicKey),
  };
}

/**
 * Sign deterministic JSON payload with Ed25519 private seed hex.
 */
export function signPayload(privateKeyHex: string, payload: any): string {
  const seed = hexToBytes(privateKeyHex);
  const keyPair = nacl.sign.keyPair.fromSeed(seed);
  const serialized = serializeForHashing(payload);
  const msgBytes = Buffer.from(serialized, 'utf-8');
  const signature = nacl.sign.detached(msgBytes, keyPair.secretKey);
  return bytesToHex(signature);
}

/**
 * Verify Ed25519 signature over deterministic payload JSON.
 */
export function verifySignature(publicKeyHex: string, payload: any, signatureHex: string): boolean {
  try {
    const pubBytes = hexToBytes(publicKeyHex);
    const sigBytes = hexToBytes(signatureHex);
    const serialized = serializeForHashing(payload);
    const msgBytes = Buffer.from(serialized, 'utf-8');
    return nacl.sign.detached.verify(msgBytes, sigBytes, pubBytes);
  } catch {
    return false;
  }
}
