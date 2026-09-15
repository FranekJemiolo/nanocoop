import {
  GENESIS_HASH,
  generateEventHash,
  generateKeyPair,
  serializeForHashing,
  signPayload,
  verifySignature,
} from '../src/utils/crypto';

describe('Teller Cryptographic Utilities', () => {
  it('serializes payloads deterministically with sorted keys and no whitespaces', () => {
    const obj1 = { z: 10, a: 1, m: { y: 2, b: 3 } };
    const obj2 = { a: 1, m: { b: 3, y: 2 }, z: 10 };

    const s1 = serializeForHashing(obj1);
    const s2 = serializeForHashing(obj2);

    expect(s1).toBe(s2);
    expect(s1).toBe('{"a":1,"m":{"b":3,"y":2},"z":10}');
  });

  it('generates valid Ed25519 keypairs and signs/verifies payloads', () => {
    const keyPair = generateKeyPair();
    expect(keyPair.privateKeyHex.length).toBe(64); // 32 bytes seed in hex
    expect(keyPair.publicKeyHex.length).toBe(64);

    const payload = {
      amount: 100.0,
      currency: 'USD',
      user_public_key: keyPair.publicKeyHex,
    };

    const signature = signPayload(keyPair.privateKeyHex, payload);
    expect(signature.length).toBe(128); // 64 bytes signature in hex

    const isValid = verifySignature(keyPair.publicKeyHex, payload, signature);
    expect(isValid).toBe(true);

    const isTampered = verifySignature(keyPair.publicKeyHex, { ...payload, amount: 200.0 }, signature);
    expect(isTampered).toBe(false);
  });

  it('generates SHA-256 event hashes chained to previous event hash', () => {
    const payloadBytes = Buffer.from(serializeForHashing({ amount: 50 }), 'utf-8');
    const signaturesBytes = Buffer.from(serializeForHashing({ teller_sig: 'abc' }), 'utf-8');

    const hash1 = generateEventHash(GENESIS_HASH, payloadBytes, signaturesBytes);
    expect(hash1.length).toBe(64);

    const hash2 = generateEventHash('1'.repeat(64), payloadBytes, signaturesBytes);
    expect(hash1).not.toBe(hash2);
  });
});
