"""Adaptive Resolver — Section VI of the NANDA paper.

This is the runtime resolver an `AgentAddr.adaptive_resolver_url` can point at.
The client hits POST /dispatch with optional context (geo region, capability
hint, etc.) and gets back a short-lived signed endpoint token telling it which
concrete endpoint to use *right now*.

MVP routing policies (paper §VI.C):
  - geo            — pick the endpoint whose region matches `client_region`
  - load           — pick least-recently-used (round-robin proxy for load)
  - capability     — pick the endpoint that advertises `requested_capability`
  - default        — round-robin

The pool of endpoints is configured per agent at startup via an env var so the
service stays stateless and demoable. In production this would be backed by a
service registry / discovery layer.

Tokens are TTL-scoped (default 60s) and signed by the resolver's own Ed25519
keypair so the downstream agent can prove the token came from a legitimate
resolver, not a forged one.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nanda.crypto import load_or_create_keypair, sign_payload


DATA_DIR = Path(os.environ.get("NANDA_DATA_DIR", "data"))
KEY_PATH = DATA_DIR / "adaptive_resolver_keypair.json"
TOKEN_TTL_SECONDS = int(os.environ.get("ADAPTIVE_TOKEN_TTL", "60"))

# Per-agent endpoint pool — JSON in an env var so docker-compose can configure
# it without code changes. Schema:
#   { "<agent_name>": [{"url": "...", "region": "us-east", "capabilities": ["echo"]}, ...] }
RAW_POOLS = os.environ.get(
    "ADAPTIVE_POOLS",
    json.dumps(
        {
            "urn:agent:demo:multiregion": [
                {
                    "url": "http://localhost:8010/echo",
                    "region": "us-east",
                    "capabilities": ["echo"],
                },
                {
                    "url": "http://localhost:8011/translate",
                    "region": "eu-west",
                    "capabilities": ["translate"],
                },
            ]
        }
    ),
)
POOLS: dict[str, list[dict]] = json.loads(RAW_POOLS)

# round-robin cursors per agent
_rr_cursor: dict[str, int] = defaultdict(int)


app = FastAPI(
    title="NANDA Adaptive Resolver",
    description="Runtime endpoint dispatcher (§VI). Returns signed, TTL-scoped routing tokens.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PRIVATE_KEY, PUBLIC_KEY = load_or_create_keypair(KEY_PATH)


class DispatchRequest(BaseModel):
    agent_name: str
    client_region: Optional[str] = Field(default=None, description="e.g. 'us-east', 'eu-west'")
    requested_capability: Optional[str] = None
    policy: str = Field(default="default", description="geo | load | capability | default")


@app.get("/")
def root():
    return {
        "service": "nanda-adaptive-resolver",
        "version": "0.1.0",
        "public_key": PUBLIC_KEY,
        "configured_agents": list(POOLS.keys()),
        "token_ttl_seconds": TOKEN_TTL_SECONDS,
    }


@app.get("/pool/{agent_name:path}")
def show_pool(agent_name: str):
    """Debug: see what endpoints the resolver knows about for this agent."""
    if agent_name not in POOLS:
        raise HTTPException(status_code=404, detail=f"no pool for {agent_name}")
    return {"agent_name": agent_name, "pool": POOLS[agent_name]}


def _pick_endpoint(agent_name: str, req: DispatchRequest) -> dict:
    pool = POOLS.get(agent_name)
    if not pool:
        raise HTTPException(status_code=404, detail=f"no pool for {agent_name}")

    if req.policy == "geo" and req.client_region:
        matches = [e for e in pool if e.get("region") == req.client_region]
        if matches:
            return matches[0]

    if req.policy == "capability" and req.requested_capability:
        matches = [
            e for e in pool if req.requested_capability in e.get("capabilities", [])
        ]
        if matches:
            return matches[0]

    # default / load — round-robin
    idx = _rr_cursor[agent_name] % len(pool)
    _rr_cursor[agent_name] = (idx + 1) % len(pool)
    return pool[idx]


@app.post("/dispatch")
def dispatch(req: DispatchRequest):
    """Pick an endpoint and return a signed, TTL-scoped routing token.

    The token is signed by the resolver, so a downstream agent can verify the
    client was actually directed here by a legitimate resolver and not making
    up its own ephemeral URL.
    """
    chosen = _pick_endpoint(req.agent_name, req)
    now = int(time.time())

    token_payload = {
        "agent_name": req.agent_name,
        "endpoint": chosen["url"],
        "region": chosen.get("region"),
        "policy_applied": req.policy,
        "issued_at": now,
        "expires_at": now + TOKEN_TTL_SECONDS,
        "resolver_pubkey": PUBLIC_KEY,
    }
    signed = sign_payload(token_payload, PRIVATE_KEY)
    return signed
