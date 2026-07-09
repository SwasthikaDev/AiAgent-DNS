"""Single-host deployment of the whole NANDA Index stack, plus an agent gateway.

The demo stack is six services (index, two facts hosts, two agents, adaptive
resolver). For a hosted submission that a vanilla agent can use from a SKILL.md,
running six URLs is a non-starter, so this module does two things:

1. Mounts every service under one FastAPI app at path prefixes, and self-registers
   the three demo agents on startup using the deployment's public URL. One process,
   one URL, the real cascade intact.

2. Adds a server-side **gateway** (`/resolve`, `/call`, `/demo/tamper`). The stack's
   trust model verifies signatures client-side (Ed25519 over JCS), which a shell
   agent cannot do. The gateway performs that verification on the server and returns
   plain JSON, so an OpenClaw agent can resolve a name, get a *verified* endpoint, and
   call it, without doing any cryptography itself.

Env: `RENDER_EXTERNAL_URL` (set automatically by Render) or `PUBLIC_BASE_URL` gives the
public base. Locally it defaults to http://localhost:8000.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# --- Public base URL. Render sets RENDER_EXTERNAL_URL; allow an override too. ---
BASE = (
    os.environ.get("PUBLIC_BASE_URL")
    or os.environ.get("RENDER_EXTERNAL_URL")
    or "http://localhost:8000"
).rstrip("/")

# --- Configure the sub-services BEFORE importing them (they read env at import). ---
os.environ.setdefault("NANDA_DATA_DIR", "data")
os.environ.setdefault("FACTS_HOST_DATA_DIR", "data/facts")
os.environ["ADAPTIVE_POOLS"] = json.dumps(
    {
        "urn:agent:demo:multiregion": [
            {"url": f"{BASE}/agent/echo", "region": "us-east", "capabilities": ["echo"]},
            {"url": f"{BASE}/agent/translate", "region": "eu-west", "capabilities": ["translate"]},
        ]
    }
)

import httpx  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from nanda.crypto import (  # noqa: E402
    generate_keypair,
    load_or_create_keypair,
    sign_vc_payload,
    verify_payload,
    verify_vc,
    verify_vc_via_did,
)
from services.adaptive_resolver.main import (  # noqa: E402
    PUBLIC_KEY as RESOLVER_TRUSTED_PUB,
    app as resolver_app,
)
from services.agents.main import app as agent_app  # noqa: E402
from services.facts_host import main as facts_main  # noqa: E402
from services.index_service.main import (  # noqa: E402
    PUBLIC_KEY as INDEX_PUB,
)
from services.index_service.main import (
    _now,
    _row_to_agent_addr,
)
from services.index_service.main import (
    app as index_app,
)
from services.index_service.main import (
    db as index_db,
)

DATA_DIR = Path(os.environ["NANDA_DATA_DIR"])
KEYS_DIR = DATA_DIR / "agent_keys"
_HERE = Path(__file__).resolve().parent
_SKILL_MD = _HERE.parent / "SKILL.md"
_INDEX_HTML = _HERE / "static" / "index.html"

# (name, agent_id, label, description, endpoint_path, facts_prefix, use_private, skills, adaptive_path)
_DEMO_AGENTS: list[tuple[str, str, str, str, str, str, bool, list[dict[str, str]], str | None]] = [
    (
        "urn:agent:demo:echo",
        "nanda:demo-echo",
        "Echo Agent",
        "Returns whatever message you send it. Useful for testing the resolution chain.",
        "/agent/echo",
        "/facts-primary",
        False,
        [{"id": "echo", "description": "Echoes the input message back."}],
        None,
    ),
    (
        "urn:agent:demo:translate",
        "nanda:demo-translate",
        "Mock Translator",
        "Uppercases the input as a stand-in for translation. Facts hosted third-party.",
        "/agent/translate",
        "/facts-private",
        True,
        [{"id": "translation", "description": "Translates short text (mock: uppercases it)."}],
        None,
    ),
    (
        "urn:agent:demo:multiregion",
        "nanda:demo-multiregion",
        "Multi-Region Agent",
        "Routed at call time by the Adaptive Resolver, which returns a signed routing token.",
        "/agent/echo",
        "/facts-primary",
        False,
        [{"id": "echo", "description": "Echoes input, dispatched to a regional pool by the resolver."}],
        "/resolver/dispatch",
    ),
]


def _register_demo_agents() -> None:
    """Register the demo agents in-process using the public base URL.

    Runs on startup instead of the docker-compose bootstrap script, and is
    idempotent, so it is safe on every boot. It calls the index DB and the facts
    host directly rather than over HTTP, because the server is not accepting
    connections yet while this runs.
    """
    for name, aid, label, desc, ep_path, facts_prefix, use_private, skills, adaptive_path in _DEMO_AGENTS:
        priv, pub = load_or_create_keypair(KEYS_DIR / f"{name.replace(':', '_')}.json")
        primary_facts_url = f"{BASE}{facts_prefix}/facts/{aid}"
        index_db.upsert_agent(
            agent_id=aid,
            agent_name=name,
            public_key=pub,
            primary_facts_url=primary_facts_url,
            private_facts_url=(primary_facts_url if use_private else None),
            adaptive_resolver_url=(f"{BASE}{adaptive_path}" if adaptive_path else None),
            ttl_seconds=3600,
            registered_at=_now(),
        )
        subject = {
            "id": aid,
            "agent_name": name,
            "label": label,
            "description": desc,
            "version": "0.1.0",
            "provider": {"name": "NANDA Demo", "url": BASE},
            "endpoints": {"static": [f"{BASE}{ep_path}"]},
            "capabilities": {
                "modalities": ["text"],
                "streaming": False,
                "authentication": {"methods": ["none"]},
            },
            "skills": skills,
            "ttl": 300,
        }
        signed_facts = sign_vc_payload(
            credential_subject=subject,
            issuer_public_key_b64=pub,
            issuer_private_key_b64=priv,
        )
        facts_main.put_facts(aid, signed_facts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _register_demo_agents()
    yield


root = FastAPI(
    title="AiAgent-DNS — NANDA Index + verified agent gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# The real stack, each service under its own prefix.
root.mount("/index", index_app)
root.mount("/facts-primary", facts_app := facts_main.app)
root.mount("/facts-private", facts_app)  # same dumb store, second prefix
root.mount("/agent", agent_app)
root.mount("/resolver", resolver_app)


def _resolve_and_verify(agent_name: str) -> dict[str, Any] | None:
    """Walk index -> AgentAddr -> AgentFacts, verifying signatures. None if unknown."""
    row = index_db.get_by_name(agent_name)
    if row is None:
        return None
    addr = _row_to_agent_addr(row).model_dump()
    addr_ok = verify_payload(addr, INDEX_PUB)
    facts: dict[str, Any] = {}
    fetch_error: str | None = None
    try:
        facts = httpx.get(addr["primary_facts_url"], timeout=8.0).json()
    except Exception as exc:  # noqa: BLE001 - report, don't crash the request
        fetch_error = str(exc)
    vc_ok = bool(facts) and verify_vc(facts, addr["public_key"])
    did_ok = bool(facts) and verify_vc_via_did(facts)
    return {
        "addr": addr,
        "facts": facts,
        "fetch_error": fetch_error,
        "addr_ok": addr_ok,
        "vc_ok": vc_ok,
        "did_ok": did_ok,
    }


class CallBody(BaseModel):
    message: str = "hello from an agent"
    region: str | None = None  # optional: route via the Adaptive Resolver for this region


class RegisterBody(BaseModel):
    name: str  # a name to publish under, e.g. urn:agent:acme:mybot
    endpoint: str  # the URL other agents should call to reach you
    label: str = ""
    description: str = ""
    skills: list[str] = []


_RESERVED = {"urn:agent:demo:echo", "urn:agent:demo:translate", "urn:agent:demo:multiregion"}


def _route_via_resolver(agent_name: str, adaptive_url: str, region: str) -> dict[str, Any] | None:
    """Ask the Adaptive Resolver for a signed routing token and verify it. None on failure."""
    try:
        token = httpx.post(
            adaptive_url,
            json={"agent_name": agent_name, "client_region": region, "policy": "geo"},
            timeout=8.0,
        ).json()
    except Exception:  # noqa: BLE001
        return None
    # Verify against the resolver key we actually trust (the in-process Adaptive
    # Resolver), NOT the pubkey the token asserts about itself. A self-certifying
    # token embeds its own key, so any keypair could otherwise mint a "valid" one
    # and repoint the endpoint. Only tokens signed by the known resolver pass.
    if not verify_payload(token, RESOLVER_TRUSTED_PUB):
        return None
    return token


@root.get("/", include_in_schema=False)
def landing():
    if _INDEX_HTML.exists():
        return FileResponse(_INDEX_HTML, media_type="text/html")
    return PlainTextResponse("AiAgent-DNS. GET /resolve/{name}, POST /call/{name}. Docs: /skill.md\n")


@root.get("/skill.md", response_class=PlainTextResponse)
@root.get("/SKILL.md", response_class=PlainTextResponse)
def skill_md() -> str:
    try:
        return _SKILL_MD.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "SKILL.md not found on server."


@root.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "aiagent-dns", "agents": len(index_db.list_agents())}


@root.get("/about")
def about() -> dict[str, Any]:
    return {
        "name": "AiAgent-DNS",
        "one_line": "Resolve an AI agent by name to a cryptographically verified endpoint, then call it.",
        "problem": "There is no DNS for AI agents. An agent cannot look up another agent by name and be "
        "sure the endpoint it gets back is authentic and untampered.",
        "why_it_matters": "This implements the NANDA 'Beyond DNS' Index: a name resolves to a signed "
        "AgentAddr, which points to a signed AgentFacts credential (W3C VC, Ed25519 over JCS). Every hop "
        "is verified, so a man-in-the-middle who swaps an endpoint is rejected. The gateway does that "
        "verification server-side so any agent can use it with plain HTTP.",
        "how_it_works": "GET /resolve/{name} returns the verified agent and its endpoint; POST /call/{name} "
        "re-verifies and calls it; POST /register publishes your own agent; GET /route/{name} shows adaptive "
        "routing with a signed token; GET /demo/tamper/{name} shows a tampered credential being rejected.",
        "primary_endpoint": "GET /resolve/urn:agent:demo:echo",
        "endpoints": [
            "GET /resolve/{name}",
            "POST /call/{name}",
            "POST /register",
            "GET /route/{name}",
            "GET /demo/tamper/{name}",
            "GET /agents",
        ],
        "skill_md": "/skill.md",
        "source": "https://github.com/SwasthikaDev/AiAgent-DNS",
        "paper": "Beyond DNS: Unlocking the Internet of AI Agents via the NANDA Index and Verified AgentFacts",
    }


@root.get("/agents")
def agents() -> dict[str, Any]:
    rows = index_db.list_agents()
    return {
        "count": len(rows),
        "agents": [
            {"agent_name": r["agent_name"], "adaptive": bool(r["adaptive_resolver_url"])} for r in rows
        ],
        "try": "GET /resolve/urn:agent:demo:echo",
    }


@root.get("/resolve/{agent_name:path}")
def gateway_resolve(agent_name: str):
    r = _resolve_and_verify(agent_name)
    if r is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": "agent_not_found",
                "message": f"No agent named '{agent_name}'.",
                "fix": "GET /agents for the list, or use urn:agent:demo:echo.",
            },
        )
    subject = r["facts"].get("credentialSubject", {})
    if not isinstance(subject, dict):
        # A tampered/malformed facts record (e.g. credentialSubject set to a string
        # via the dumb facts store) must not crash the resolve. Its signature won't
        # verify against the index key, so verified is already False below.
        subject = {}
    return {
        "status": "ok",
        "agent_name": agent_name,
        "verified": bool(r["addr_ok"] and r["vc_ok"]),
        "verification": {
            "agent_addr_signature": r["addr_ok"],
            "agent_facts_vc": r["vc_ok"],
            "did_key_self_verify": r["did_ok"],
            "cryptosuite": r["facts"].get("proof", {}).get("cryptosuite"),
        },
        "agent": {
            "label": subject.get("label"),
            "description": subject.get("description"),
            "endpoint": (subject.get("endpoints", {}).get("static") or [None])[0],
            "skills": [s.get("id") for s in subject.get("skills", [])],
            "adaptive_resolver_url": r["addr"].get("adaptive_resolver_url"),
        },
        "chain": [
            "index resolves the name to a signed AgentAddr",
            "AgentAddr signature checked against the index key",
            "AgentFacts credential fetched from the AgentAddr",
            "credential signature checked against the agent key and its did:key",
        ],
        "next_step": f"POST /call/{agent_name} with a JSON body to send it a message.",
    }


@root.post("/call/{agent_name:path}")
def gateway_call(agent_name: str, body: CallBody):
    r = _resolve_and_verify(agent_name)
    if r is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": "agent_not_found",
                "message": f"No agent named '{agent_name}'.",
                "fix": "GET /agents for the list, or use urn:agent:demo:echo.",
            },
        )
    if not (r["addr_ok"] and r["vc_ok"]):
        return {
            "status": "refused",
            "verified": False,
            "reason": "Signature verification failed; refusing to call a possibly-tampered endpoint.",
        }
    endpoint = r["facts"]["credentialSubject"]["endpoints"]["static"][0]
    routing: dict[str, Any] | None = None
    adaptive_url = r["addr"].get("adaptive_resolver_url")
    if body.region and adaptive_url:
        token = _route_via_resolver(agent_name, adaptive_url, body.region)
        if token is not None:
            endpoint = token["endpoint"]
            routing = {
                "via": "adaptive-resolver",
                "region": token.get("region"),
                "policy_applied": token.get("policy_applied"),
                "routing_token_verified": True,
                "expires_at": token.get("expires_at"),
            }
    try:
        resp = httpx.post(endpoint, json={"message": body.message}, timeout=8.0).json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": f"call to verified endpoint failed: {exc}"}
    return {
        "status": "ok",
        "verified": True,
        "endpoint_called": endpoint,
        "routing": routing,
        "agent_response": resp,
        "note": "The endpoint was cryptographically verified before the call was made.",
    }


@root.get("/route/{agent_name:path}")
def gateway_route(agent_name: str, region: str = "us-east"):
    """Show adaptive routing: the resolver returns a signed, TTL-scoped endpoint token."""
    r = _resolve_and_verify(agent_name)
    if r is None:
        return JSONResponse(
            status_code=404, content={"error": "agent_not_found", "fix": "Use urn:agent:demo:multiregion."}
        )
    adaptive_url = r["addr"].get("adaptive_resolver_url")
    if not adaptive_url:
        return {
            "status": "no_adaptive_routing",
            "message": f"{agent_name} has a static endpoint, not an adaptive resolver.",
            "static_endpoint": r["facts"]["credentialSubject"]["endpoints"]["static"][0],
            "try": "urn:agent:demo:multiregion has adaptive routing.",
        }
    token = _route_via_resolver(agent_name, adaptive_url, region)
    if token is None:
        return {"status": "error", "reason": "adaptive resolver did not return a valid signed token"}
    return {
        "status": "ok",
        "agent_name": agent_name,
        "requested_region": region,
        "routing_token_verified": True,
        "endpoint": token["endpoint"],
        "region": token.get("region"),
        "policy_applied": token.get("policy_applied"),
        "expires_at": token.get("expires_at"),
        "note": "The resolver signed this endpoint choice; a downstream agent can prove the routing "
        "came from a legitimate resolver, not a forged URL.",
    }


@root.post("/register")
def gateway_register(body: RegisterBody):
    """Publish an agent under a name so any other agent can resolve and verify it.

    The gateway generates the agent's signing key, writes a signed AgentFacts
    credential, and registers it in the index. It is then resolvable at
    /resolve/{name} exactly like the built-in demos. (Registrations live for the
    duration of this deployment; the built-in demos re-register on restart.)
    """
    name = body.name.strip()
    endpoint = body.endpoint.strip()
    if not name or not endpoint:
        return JSONResponse(
            status_code=400,
            content={
                "error": "missing_fields",
                "message": "Both 'name' and 'endpoint' are required.",
                "fix": "Send {\"name\": \"urn:agent:acme:mybot\", \"endpoint\": \"https://.../call\"}.",
            },
        )
    if name in _RESERVED:
        return JSONResponse(
            status_code=409,
            content={
                "error": "reserved_name",
                "message": f"'{name}' is a built-in demo agent.",
                "fix": "Choose a different name, e.g. urn:agent:acme:mybot.",
            },
        )
    if index_db.get_by_name(name) is not None:
        # Names are immutable once registered. Without this check a second
        # /register for the same name would overwrite the index row and facts
        # (upsert is delete-then-insert), letting a caller repoint a previously
        # verified endpoint to their own URL under a freshly minted valid key.
        return JSONResponse(
            status_code=409,
            content={
                "error": "name_taken",
                "message": f"'{name}' is already registered.",
                "fix": "Choose a different, unused name (registrations are immutable in this deployment).",
            },
        )
    aid = "nanda:" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]  # noqa: S324 - id, not security
    priv, pub = generate_keypair()
    primary_facts_url = f"{BASE}/facts-primary/facts/{aid}"
    index_db.upsert_agent(
        agent_id=aid,
        agent_name=name,
        public_key=pub,
        primary_facts_url=primary_facts_url,
        private_facts_url=None,
        adaptive_resolver_url=None,
        ttl_seconds=3600,
        registered_at=_now(),
    )
    subject = {
        "id": aid,
        "agent_name": name,
        "label": body.label or name,
        "description": body.description or "Registered via /register.",
        "version": "0.1.0",
        "provider": {"name": "self-registered", "url": BASE},
        "endpoints": {"static": [endpoint]},
        "capabilities": {"modalities": ["text"], "streaming": False, "authentication": {"methods": ["none"]}},
        "skills": ([{"id": s, "description": s} for s in body.skills] or [{"id": "custom", "description": "Registered agent."}]),
        "ttl": 300,
    }
    signed = sign_vc_payload(credential_subject=subject, issuer_public_key_b64=pub, issuer_private_key_b64=priv)
    facts_main.put_facts(aid, signed)
    return {
        "status": "ok",
        "registered": True,
        "agent_name": name,
        "resolve": f"/resolve/{name}",
        "note": "Your agent is now resolvable and its endpoint is signed. Any agent can GET "
        f"/resolve/{name} to verify and reach it. The gateway generated and holds the signing key "
        "for this demo.",
    }


@root.get("/demo/tamper/{agent_name:path}")
def gateway_tamper(agent_name: str):
    r = _resolve_and_verify(agent_name)
    if r is None or not r["facts"]:
        return JSONResponse(
            status_code=404,
            content={"error": "agent_not_found", "fix": "Use urn:agent:demo:echo."},
        )
    facts = json.loads(json.dumps(r["facts"]))  # deep copy
    original = facts["credentialSubject"]["endpoints"]["static"][0]
    facts["credentialSubject"]["endpoints"]["static"][0] = "http://evil.example.com/steal"
    still_valid = verify_vc(facts, r["addr"]["public_key"])
    return {
        "status": "ok",
        "tampered_field": "credentialSubject.endpoints.static[0]",
        "original_endpoint": original,
        "tampered_to": "http://evil.example.com/steal",
        "vc_still_verifies": still_valid,
        "result": "rejected" if not still_valid else "ACCEPTED (this would be a bug)",
        "explanation": "Swapping the endpoint changes the JCS-canonical bytes of the credential, so the "
        "Ed25519 signature no longer matches. Without the agent's private key an attacker cannot forge a "
        "new one, so verification fails and the endpoint is refused.",
    }


@root.exception_handler(404)
async def not_found(request: Request, exc) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "route_not_found",
            "message": f"No route for {request.method} {request.url.path}.",
            "fix": "Valid routes: GET /resolve/{name}, POST /call/{name}, GET /demo/tamper/{name}, GET /agents, GET /health.",
        },
    )
