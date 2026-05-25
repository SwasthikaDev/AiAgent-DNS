"""Ed25519 signing and verification over canonical JSON.

We sign canonical JSON (RFC 8785 JCS) so that any verifier that re-canonicalizes
the same payload reproduces the same bytes — sigs survive whitespace and key-order
shuffling. This is the same primitive W3C Verifiable Credentials use; for the MVP
we ship just the signature without the full VC envelope.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from nacl import signing
from nacl.exceptions import BadSignatureError


SIGNATURE_FIELD = "signature"


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def generate_keypair() -> tuple[str, str]:
    """Return (private_key_b64, public_key_b64)."""
    sk = signing.SigningKey.generate()
    return _b64e(sk.encode()), _b64e(sk.verify_key.encode())


def load_or_create_keypair(path: Path) -> tuple[str, str]:
    """Read a keypair from disk, or generate and persist one if missing.

    Stored as JSON: {"private": "...", "public": "..."}
    """
    if path.exists():
        data = json.loads(path.read_text())
        return data["private"], data["public"]

    priv, pub = generate_keypair()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"private": priv, "public": pub}, indent=2))
    return priv, pub


def canonicalize(payload: dict[str, Any]) -> bytes:
    """RFC 8785-ish canonical JSON: sorted keys, no whitespace, UTF-8.

    Pure JCS also dictates number formatting; for our payloads (strings, ints,
    nested objects, no floats) Python's default JSON output with these flags
    matches JCS byte-for-byte.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sign_payload(payload: dict[str, Any], private_key_b64: str) -> dict[str, Any]:
    """Return a copy of `payload` with a `signature` field appended.

    The signature covers the canonicalized payload with the signature field
    omitted — standard detached-signature pattern.
    """
    unsigned = {k: v for k, v in payload.items() if k != SIGNATURE_FIELD}
    sk = signing.SigningKey(_b64d(private_key_b64))
    sig = sk.sign(canonicalize(unsigned)).signature
    return {**unsigned, SIGNATURE_FIELD: _b64e(sig)}


def verify_payload(signed: dict[str, Any], public_key_b64: str) -> bool:
    """Return True iff `signed[SIGNATURE_FIELD]` is a valid sig over the rest."""
    if SIGNATURE_FIELD not in signed:
        return False

    sig_b64 = signed[SIGNATURE_FIELD]
    unsigned = {k: v for k, v in signed.items() if k != SIGNATURE_FIELD}

    try:
        vk = signing.VerifyKey(_b64d(public_key_b64))
        vk.verify(canonicalize(unsigned), _b64d(sig_b64))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False
