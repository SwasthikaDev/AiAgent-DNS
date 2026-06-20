"""Sanity tests for the signing layer.

Run: python -m pytest tests/ -q
(pytest is not in requirements.txt — install ad-hoc: pip install pytest)
"""

from nanda.crypto import (
    CRYPTOSUITE,
    canonicalize,
    did_key_to_pubkey_b64,
    generate_keypair,
    pubkey_to_did_key,
    sign_payload,
    sign_vc_payload,
    verify_payload,
    verify_vc,
    verify_vc_via_did,
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


# --- W3C VC envelope tests --------------------------------------------------


def test_vc_roundtrip():
    priv, pub = generate_keypair()
    subject = {"id": "nanda:abc", "label": "Test Agent", "skills": ["echo"]}
    vc = sign_vc_payload(
        credential_subject=subject,
        issuer_public_key_b64=pub,
        issuer_private_key_b64=priv,
    )
    assert vc["proof"]["cryptosuite"] == CRYPTOSUITE
    assert vc["type"] == ["VerifiableCredential", "AgentFactsCredential"]
    assert vc["credentialSubject"] == subject
    assert verify_vc(vc, pub) is True


def test_vc_tamper_detected():
    priv, pub = generate_keypair()
    vc = sign_vc_payload(
        credential_subject={"id": "x", "label": "x"},
        issuer_public_key_b64=pub,
        issuer_private_key_b64=priv,
    )
    vc["credentialSubject"]["label"] = "tampered"
    assert verify_vc(vc, pub) is False


def test_vc_wrong_key_rejected():
    priv1, _ = generate_keypair()
    _, pub2 = generate_keypair()
    vc = sign_vc_payload(
        credential_subject={"id": "x"},
        issuer_public_key_b64=pub2,  # mismatched on purpose
        issuer_private_key_b64=priv1,
    )
    assert verify_vc(vc, pub2) is False


# --- did:key resolution tests ----------------------------------------------


def test_did_key_roundtrip():
    _, pub = generate_keypair()
    did = pubkey_to_did_key(pub)
    assert did.startswith("did:key:z")
    # The key recovered from the identifier matches the original, byte-for-byte.
    assert did_key_to_pubkey_b64(did) == pub


def test_vc_verifies_via_did_with_no_external_key():
    priv, pub = generate_keypair()
    vc = sign_vc_payload(
        credential_subject={"id": "nanda:abc", "label": "DID Agent"},
        issuer_public_key_b64=pub,
        issuer_private_key_b64=priv,
    )
    # The VC self-describes its issuer as a did:key...
    assert vc["issuer"].startswith("did:key:z")
    # ...so the client can verify it without being handed the public key.
    assert verify_vc_via_did(vc) is True


def test_vc_via_did_tamper_detected():
    priv, pub = generate_keypair()
    vc = sign_vc_payload(
        credential_subject={"id": "x", "label": "ok"},
        issuer_public_key_b64=pub,
        issuer_private_key_b64=priv,
    )
    vc["credentialSubject"]["label"] = "tampered"
    assert verify_vc_via_did(vc) is False
