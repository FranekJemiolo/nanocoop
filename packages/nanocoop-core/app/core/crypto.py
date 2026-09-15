"""Cryptographic primitives and Ed25519 PKI utilities for NanoCoop."""

import hashlib
import json
from typing import Any
import nacl.encoding
import nacl.signing
import nacl.exceptions

GENESIS_HASH = "0" * 64


def serialize_for_hashing(payload: dict[str, Any]) -> bytes:
    """Strictly enforce sort_keys=True and separators=(',', ':') for deterministic cross-platform hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def generate_event_hash(previous_hash: str, payload_bytes: bytes, signatures_bytes: bytes) -> str:
    """Compute SHA-256(previous_hash + payload + signatures)."""
    hasher = hashlib.sha256()
    hasher.update(previous_hash.encode("utf-8"))
    hasher.update(payload_bytes)
    hasher.update(signatures_bytes)
    return hasher.hexdigest()


def generate_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair. Returns (private_key_hex, public_key_hex)."""
    signing_key = nacl.signing.SigningKey.generate()
    private_hex = signing_key.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8")
    public_hex = signing_key.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode("utf-8")
    return private_hex, public_hex


def sign_payload(private_key_hex: str, payload: dict[str, Any]) -> str:
    """Sign deterministic JSON payload with Ed25519 private key. Returns signature hex string."""
    signing_key = nacl.signing.SigningKey(
        private_key_hex.encode("utf-8"), encoder=nacl.encoding.HexEncoder
    )
    payload_bytes = serialize_for_hashing(payload)
    signed = signing_key.sign(payload_bytes)
    return signed.signature.hex()


def verify_signature(public_key_hex: str, payload: dict[str, Any], signature_hex: str) -> bool:
    """Verify Ed25519 signature over deterministic payload JSON."""
    try:
        verify_key = nacl.signing.VerifyKey(
            public_key_hex.encode("utf-8"), encoder=nacl.encoding.HexEncoder
        )
        payload_bytes = serialize_for_hashing(payload)
        signature_bytes = bytes.fromhex(signature_hex)
        verify_key.verify(payload_bytes, signature_bytes)
        return True
    except (nacl.exceptions.BadSignatureError, ValueError, Exception):
        return False


def hash_leaf(data: str) -> str:
    """Compute SHA-256 leaf hash for Merkle tree."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash_pair(left: str, right: str) -> str:
    """Compute SHA-256 of combined parent node."""
    hasher = hashlib.sha256()
    hasher.update(left.encode("utf-8"))
    hasher.update(right.encode("utf-8"))
    return hasher.hexdigest()


def compute_merkle_root(leaf_hashes: list[str]) -> str:
    """Compute the Merkle Tree root hash from an ordered list of leaf event hashes.

    If empty, returns GENESIS_HASH.
    If odd number of leaves, the last leaf is duplicated to form a balanced tree.
    """
    if not leaf_hashes:
        return GENESIS_HASH

    current_layer = [hash_leaf(h) for h in leaf_hashes]

    while len(current_layer) > 1:
        next_layer: list[str] = []
        for i in range(0, len(current_layer), 2):
            left = current_layer[i]
            right = current_layer[i + 1] if i + 1 < len(current_layer) else left
            next_layer.append(hash_pair(left, right))
        current_layer = next_layer

    return current_layer[0]
