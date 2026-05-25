"""Ed25519 signing and verification over canonical JSON.

We sign canonical JSON (RFC 8785 JCS) so that any verifier that re-canonicalizes
the same payload reproduces the same bytes — sigs survive whitespace and key-order
shuffling.

Two signing modes:

- `sign_payload` / `verify_payload`: detached signature in a top-level "signature"
  field. Used for AgentAddr (an index resolver record, not a credential about
  an agent).

- `sign_vc_payload` / `verify_vc`: W3C Verifiable Credential v2 envelope with
  a DataIntegrityProof using the `eddsa-jcs-2022` cryptosuite. Used for
  AgentFacts (which IS a credential about an agent — what the paper calls a
  "verifiable claim"). The cryptosuite is exactly Ed25519 over JCS — i.e. the
  same primitive as above, just wrapped per the W3C spec so the wire format
  is interoperable with any VC-aware verifier.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nacl import signing
from nacl.exceptions import BadSignatureError


SIGNATURE_FIELD = "signature"

# W3C VC v2 context + cryptosuite identifiers.
VC_V2_CONTEXT = "https://www.w3.org/ns/credentials/v2"
DATA_INTEGRITY_CONTEXT = "https://w3id.org/security/data-integrity/v2"
CRYPTOSUITE = "eddsa-jcs-2022"  # Ed25519 over JCS — same primitive we use


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


# ============================================================================
# W3C Verifiable Credential v2 helpers — DataIntegrityProof / eddsa-jcs-2022
# ============================================================================


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sign_vc_payload(
    *,
    credential_subject: dict[str, Any],
    issuer_public_key_b64: str,
    issuer_private_key_b64: str,
    credential_type: str = "AgentFactsCredential",
) -> dict[str, Any]:
    """Wrap a payload as a W3C VC v2 with a DataIntegrityProof.

    The proof's `proofValue` covers the JCS-canonicalized credential with the
    `proof` block omitted entirely — the standard pattern for DataIntegrityProof.
    """
    issued_at = _now_iso()
    credential = {
        "@context": [VC_V2_CONTEXT, DATA_INTEGRITY_CONTEXT],
        "type": ["VerifiableCredential", credential_type],
        "issuer": f"key:{issuer_public_key_b64}",
        "validFrom": issued_at,
        "credentialSubject": credential_subject,
    }

    sk = signing.SigningKey(_b64d(issuer_private_key_b64))
    sig = sk.sign(canonicalize(credential)).signature

    credential["proof"] = {
        "type": "DataIntegrityProof",
        "cryptosuite": CRYPTOSUITE,
        "created": issued_at,
        "verificationMethod": f"key:{issuer_public_key_b64}",
        "proofPurpose": "assertionMethod",
        "proofValue": _b64e(sig),
    }
    return credential


def verify_vc(credential: dict[str, Any], public_key_b64: str) -> bool:
    """Verify a DataIntegrityProof VC against a known public key.

    Strips the `proof` block, re-canonicalizes, and Ed25519-verifies.
    """
    proof = credential.get("proof")
    if not proof or proof.get("cryptosuite") != CRYPTOSUITE:
        return False

    proof_value = proof.get("proofValue")
    if not proof_value:
        return False

    unsigned = {k: v for k, v in credential.items() if k != "proof"}

    try:
        vk = signing.VerifyKey(_b64d(public_key_b64))
        vk.verify(canonicalize(unsigned), _b64d(proof_value))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False
