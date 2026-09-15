"""Cryptographic and deterministic serialization unit tests."""

import pytest
from app.core.crypto import (
    GENESIS_HASH,
    compute_merkle_root,
    generate_event_hash,
    generate_keypair,
    serialize_for_hashing,
    sign_payload,
    verify_signature,
)


def test_deterministic_serialization():
    """Verify deterministic JSON serialization ignores key order and whitespaces."""
    dict1 = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    dict2 = {"nested": {"y": 8, "z": 9}, "a": 1, "b": 2}

    bytes1 = serialize_for_hashing(dict1)
    bytes2 = serialize_for_hashing(dict2)

    assert bytes1 == bytes2
    assert bytes1 == b'{"a":1,"b":2,"nested":{"y":8,"z":9}}'


def test_ed25519_sign_and_verify():
    """Verify Ed25519 signing and verification with valid and tampered payloads."""
    priv, pub = generate_keypair()
    payload = {"amount": 50.0, "currency": "USD", "user_public_key": pub}

    sig = sign_payload(priv, payload)
    assert len(sig) == 128  # 64 bytes in hex

    # Verify succeeds with original payload
    assert verify_signature(pub, payload, sig) is True

    # Tampered payload fails verification
    tampered_payload = {"amount": 100.0, "currency": "USD", "user_public_key": pub}
    assert verify_signature(pub, tampered_payload, sig) is False

    # Wrong public key fails verification
    _, other_pub = generate_keypair()
    assert verify_signature(other_pub, payload, sig) is False

    # Corrupted signature fails verification
    corrupted_sig = "00" * 64
    assert verify_signature(pub, payload, corrupted_sig) is False


def test_event_hash_generation():
    """Verify SHA-256 hash generation chaining."""
    prev_hash = GENESIS_HASH
    payload = {"amount": 25.0}
    signatures = {"teller_sig": "abc"}

    p_bytes = serialize_for_hashing(payload)
    s_bytes = serialize_for_hashing(signatures)

    hash1 = generate_event_hash(prev_hash, p_bytes, s_bytes)
    assert len(hash1) == 64

    # Different previous hash changes result
    hash2 = generate_event_hash("1" * 64, p_bytes, s_bytes)
    assert hash1 != hash2


def test_merkle_tree_computation():
    """Verify Merkle tree root calculation under empty, single, even, and odd leaf sets."""
    # Empty
    assert compute_merkle_root([]) == GENESIS_HASH

    # Single leaf
    leaf1 = "a" * 64
    root1 = compute_merkle_root([leaf1])
    assert len(root1) == 64

    # Even leaves
    leaf2 = "b" * 64
    root_even = compute_merkle_root([leaf1, leaf2])
    assert len(root_even) == 64
    assert root_even != root1

    # Odd leaves (balances by duplicating last leaf)
    leaf3 = "c" * 64
    root_odd = compute_merkle_root([leaf1, leaf2, leaf3])
    assert len(root_odd) == 64
    assert root_odd != root_even
