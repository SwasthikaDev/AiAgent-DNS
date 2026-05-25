"""Sanity tests for the signing layer.

Run: python -m pytest tests/ -q
(pytest is not in requirements.txt — install ad-hoc: pip install pytest)
"""

from nanda.crypto import (
    canonicalize,
    generate_keypair,
    sign_payload,
    verify_payload,
)


def test_roundtrip():
    priv, pub = generate_keypair()
    payload = {"b": 2, "a": 1, "nested": {"y": 9, "x": 8}}
    signed = sign_payload(payload, priv)
    assert verify_payload(signed, pub) is True


def test_tamper_detected():
    priv, pub = generate_keypair()
    signed = sign_payload({"hello": "world"}, priv)
    signed["hello"] = "tampered"
    assert verify_payload(signed, pub) is False


def test_wrong_key_rejected():
    priv1, _ = generate_keypair()
    _, pub2 = generate_keypair()
    signed = sign_payload({"x": 1}, priv1)
    assert verify_payload(signed, pub2) is False


def test_canonicalization_is_key_order_insensitive():
    a = canonicalize({"a": 1, "b": 2})
    b = canonicalize({"b": 2, "a": 1})
    assert a == b
