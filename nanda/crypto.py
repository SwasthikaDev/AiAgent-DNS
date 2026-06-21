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


# Keys and signatures are raw bytes; JSON can't carry bytes, so everything that
# crosses the wire (or lands in a record) is base64-encoded text.
def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def generate_keypair() -> tuple[str, str]:
    """Return (private_key_b64, public_key_b64)."""
    sk = signing.SigningKey.generate() # generates the private key
    # verify_key creates the public key
    return _b64e(sk.encode()), _b64e(sk.verify_key.encode())
    # The Ed25519 public (verify) key is derived from the private (signing) key.
    # Ed25519 generates both key pair and signature


def load_or_create_keypair(path: Path) -> tuple[str, str]:
    """Read a keypair from disk, or generate and persist one if missing.

    Stored as JSON: {"private": "...", "public": "..."}

    Persisting matters: a service's key is its stable identity. If the index (or
    resolver) regenerated a key on every restart, every record it had already
    signed would stop verifying — so we keep the same key across restarts.
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
    # Sign over everything EXCEPT the signature field (it doesn't exist yet at
    # sign time, and stripping it lets verify reproduce the exact same bytes).
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
        # A bad signature (or malformed key/sig) is an expected outcome, not a
        # crash — return False so callers just get a yes/no answer.
        return False


# ============================================================================
# did:key resolution — derive an agent's verify key from its own identifier
# ============================================================================
#
# A did:key encodes the public key INSIDE the identifier, so resolving it needs
# no network and no storage:  did:key:z<base58btc(0xed01 || raw_pubkey)>.
# This lets a client recover the agent's Ed25519 key straight from the VC's
# verificationMethod — the paper's trust model — instead of trusting a copy of
# the key handed out by the index. (base58 is an encoding, not a crypto step,
# so it's fine to implement inline; the actual signing/verifying is still PyNaCl.)

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# Multicodec prefix tagging the bytes as an Ed25519 public key
# (0xed = ed25519-pub, 0x01 = varint continuation). Mandated by the did:key spec.
_ED25519_MULTICODEC = b"\xed\x01"


def _b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n > 0:
        n, rem = divmod(n, 58)
        out = _B58_ALPHABET[rem] + out
    # Each leading zero byte is preserved as a leading '1'.
    pad = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * pad + out


def _b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + _B58_ALPHABET.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + body


def pubkey_to_did_key(public_key_b64: str) -> str:
    """Encode an Ed25519 public key as a did:key identifier.

    did:key:z<base58btc(0xed01 || 32-byte raw pubkey)>
    """
    raw = _b64d(public_key_b64)
    return "did:key:z" + _b58encode(_ED25519_MULTICODEC + raw)


def did_key_to_pubkey_b64(did: str) -> str:
    """Recover the base64 Ed25519 public key from a did:key identifier.

    Accepts an optional fragment (e.g. did:key:zABC#zABC) and ignores it.
    """
    did = did.split("#", 1)[0]
    if not did.startswith("did:key:z"):
        raise ValueError(f"not a did:key identifier: {did!r}")
    data = _b58decode(did[len("did:key:z"):])
    if data[:2] != _ED25519_MULTICODEC:
        raise ValueError("did:key does not encode an Ed25519 key")
    return _b64e(data[2:])


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
    # Identify the issuer by its did:key, so a verifier can recover the key from
    # the credential itself (see verify_vc_via_did) — no index-supplied key needed.
    issuer_did = pubkey_to_did_key(issuer_public_key_b64)
    credential = {
        "@context": [VC_V2_CONTEXT, DATA_INTEGRITY_CONTEXT],
        "type": ["VerifiableCredential", credential_type],
        "issuer": issuer_did,
        "validFrom": issued_at,
        "credentialSubject": credential_subject,
    }

    # Sign the credential BEFORE the proof block exists. verify_vc later strips
    # `proof` back off to reproduce these exact bytes.
    sk = signing.SigningKey(_b64d(issuer_private_key_b64))
    sig = sk.sign(canonicalize(credential)).signature

    credential["proof"] = {
        "type": "DataIntegrityProof",
        "cryptosuite": CRYPTOSUITE,
        "created": issued_at,
        # did:key fragment form: did:key:zABC#zABC (the spec's verificationMethod).
        "verificationMethod": f"{issuer_did}#{issuer_did.removeprefix('did:key:')}",
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

    # Strip `proof` and re-canonicalize to recover the exact bytes that were
    # signed. This is what catches tampering: mutate any field in
    # credentialSubject and these bytes no longer match proofValue → verify fails.
    unsigned = {k: v for k, v in credential.items() if k != "proof"}

    try:
        vk = signing.VerifyKey(_b64d(public_key_b64))
        vk.verify(canonicalize(unsigned), _b64d(proof_value))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def verify_vc_via_did(credential: dict[str, Any]) -> bool:
    """Verify a VC by resolving the issuer key from its own did:key.

    Unlike verify_vc(credential, public_key), this needs NO external key: it
    reads proof.verificationMethod (a did:key), decodes the Ed25519 public key
    out of that identifier, and verifies against it. This is the paper-faithful
    path — the client trusts the credential's self-described issuer DID rather
    than a public-key copy handed out by the index.
    """
    proof = credential.get("proof") or {}
    try:
        pub_b64 = did_key_to_pubkey_b64(proof.get("verificationMethod", ""))
    except (ValueError, KeyError):
        return False
    return verify_vc(credential, pub_b64)
