"""Bootstrap two demo agents into a running NANDA stack.

After `docker compose up` finishes, run this once to:
  1. Generate a keypair per agent (persisted under data/agent_keys/).
  2. Register each agent with the index service.
  3. Publish each agent's signed AgentFacts to its facts host.

Agent A (echo) — primary facts host (agent-owned style).
Agent B (translate) — private facts host (third-party / privacy path).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Allow running this script directly (python scripts/bootstrap.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nanda.crypto import load_or_create_keypair, sign_vc_payload  # noqa: E402


INDEX_URL = os.environ.get("INDEX_URL", "http://localhost:8000")
PRIMARY_FACTS_URL = os.environ.get("PRIMARY_FACTS_URL", "http://localhost:8001")
PRIVATE_FACTS_URL = os.environ.get("PRIVATE_FACTS_URL", "http://localhost:8002")
ECHO_AGENT_URL = os.environ.get("ECHO_AGENT_URL", "http://localhost:8010")
TRANSLATE_AGENT_URL = os.environ.get("TRANSLATE_AGENT_URL", "http://localhost:8011")
ADAPTIVE_RESOLVER_URL = os.environ.get("ADAPTIVE_RESOLVER_URL", "http://localhost:8020")

KEYS_DIR = Path(os.environ.get("KEYS_DIR", "data/agent_keys"))


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def register_agent(
    *,
    agent_name: str,
    label: str,
    description: str,
    endpoint: str,
    facts_host_url: str,
    use_private: bool,
    skills: list[dict],
    capabilities: dict,
    adaptive_resolver_url: str | None = None,
) -> None:
    print(f"\n=== Registering {agent_name} ===")

    priv, pub = load_or_create_keypair(KEYS_DIR / f"{agent_name.replace(':', '_')}.json")
    print(f"  pubkey: {pub[:24]}...")

    # 1) Register with the index. PUT is idempotent so re-running is safe.
    facts_url_field = "primary_facts_url"  # always set primary
    register_body = {
        "agent_name": agent_name,
        "public_key": pub,
        facts_url_field: f"{facts_host_url}/facts/PLACEHOLDER",
        "ttl": 3600,
    }
    if use_private:
        register_body["private_facts_url"] = f"{facts_host_url}/facts/PLACEHOLDER"
    if adaptive_resolver_url:
        register_body["adaptive_resolver_url"] = adaptive_resolver_url

    # First call to get the assigned agent_id.
    r = httpx.put(f"{INDEX_URL}/register", json=register_body, timeout=10.0)
    r.raise_for_status()
    addr = r.json()
    agent_id = addr["agent_id"]
    print(f"  agent_id: {agent_id}")

    # 2) Now that we know the agent_id, re-register with the correct facts URL.
    register_body["primary_facts_url"] = f"{facts_host_url}/facts/{agent_id}"
    if use_private:
        register_body["private_facts_url"] = f"{facts_host_url}/facts/{agent_id}"
    if adaptive_resolver_url:
        register_body["adaptive_resolver_url"] = adaptive_resolver_url

    r = httpx.put(f"{INDEX_URL}/register", json=register_body, timeout=10.0)
    r.raise_for_status()
    addr = r.json()
    print(f"  registered with facts at: {addr['primary_facts_url']}")

    # 3) Build the AgentFacts subject and sign it as a W3C VC v2.
    subject = {
        "id": agent_id,
        "agent_name": agent_name,
        "label": label,
        "description": description,
        "version": "0.1.0",
        "provider": {"name": "NANDA Demo", "url": "http://localhost"},
        "endpoints": {"static": [endpoint]},
        "capabilities": capabilities,
        "skills": skills,
        "ttl": 300,
    }
    signed_facts = sign_vc_payload(
        credential_subject=subject,
        issuer_public_key_b64=pub,
        issuer_private_key_b64=priv,
    )

    # 4) PUT the signed facts to the host.
    r = httpx.put(
        f"{facts_host_url}/facts/{agent_id}", json=signed_facts, timeout=10.0
    )
    r.raise_for_status()
    print(f"  facts published to: {facts_host_url}/facts/{agent_id}")
    print(f"  [OK] {agent_name} ready to resolve")


def main():
    print(f"INDEX_URL          = {INDEX_URL}")
    print(f"PRIMARY_FACTS_URL  = {PRIMARY_FACTS_URL}")
    print(f"PRIVATE_FACTS_URL  = {PRIVATE_FACTS_URL}")

    # Agent A — NANDA-native style. Facts live on its own (primary) host.
    register_agent(
        agent_name="urn:agent:demo:echo",
        label="Echo Agent",
        description="Returns whatever you send it. Useful for testing routing.",
        endpoint=f"{ECHO_AGENT_URL}/echo",
        facts_host_url=PRIMARY_FACTS_URL,
        use_private=False,
        skills=[
            {"id": "echo", "description": "Echoes the input message back."}
        ],
        capabilities={
            "modalities": ["text"],
            "streaming": False,
            "authentication": {"methods": ["none"]},
        },
    )

    # Agent B — third-party-hosted facts (private/quilt-style registration).
    register_agent(
        agent_name="urn:agent:demo:translate",
        label="Mock Translator",
        description="Pretend translator that uppercases the input.",
        endpoint=f"{TRANSLATE_AGENT_URL}/translate",
        facts_host_url=PRIVATE_FACTS_URL,
        use_private=True,
        skills=[
            {
                "id": "translation",
                "description": "Translates short text between languages.",
            }
        ],
        capabilities={
            "modalities": ["text"],
            "streaming": False,
            "authentication": {"methods": ["none"]},
        },
    )

    # Agent C — adaptive routing (§VI of the paper). Resolves to a signed
    # routing token issued by the AdaptiveResolver, not a static endpoint.
    register_agent(
        agent_name="urn:agent:demo:multiregion",
        label="Multi-Region Agent",
        description="Routed dynamically by the Adaptive Resolver across regions.",
        endpoint=f"{ECHO_AGENT_URL}/echo",  # fallback static endpoint
        facts_host_url=PRIMARY_FACTS_URL,
        use_private=False,
        skills=[
            {
                "id": "echo",
                "description": "Echoes input — dispatched to a regional pool by the resolver.",
            }
        ],
        capabilities={
            "modalities": ["text"],
            "streaming": False,
            "authentication": {"methods": ["none"]},
        },
        adaptive_resolver_url=f"{ADAPTIVE_RESOLVER_URL}/dispatch",
    )

    print("\nAll demo agents registered. Try:")
    print("  python -m nanda.cli list")
    print("  python -m nanda.cli resolve urn:agent:demo:echo")
    print('  python -m nanda.cli call urn:agent:demo:echo --message "hello"')
    print("  python -m nanda.cli call urn:agent:demo:multiregion --adaptive")
    print("  python -m nanda.cli demo-tamper urn:agent:demo:echo")


if __name__ == "__main__":
    main()
