"""NANDA Index Service.

The lean anchor tier from §IV of the paper. Holds a tiny record per agent
and returns it as a signed AgentAddr. Anyone who has this service's public
key can verify that an AgentAddr really came from here.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException

from nanda.crypto import load_or_create_keypair, sign_payload
from nanda.schemas import AgentAddr, RegisterRequest

from .db import IndexDB


DATA_DIR = Path(os.environ.get("NANDA_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "index.sqlite"
KEY_PATH = DATA_DIR / "index_keypair.json"

app = FastAPI(
    title="NANDA Index Service",
    description="Lean anchor tier — maps agent names to signed AgentAddr records.",
    version="0.1.0",
)

db = IndexDB(DB_PATH)
PRIVATE_KEY, PUBLIC_KEY = load_or_create_keypair(KEY_PATH)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _row_to_agent_addr(row) -> AgentAddr:
    payload = {
        "agent_id": row["agent_id"],
        "agent_name": row["agent_name"],
        "public_key": row["public_key"],
        "primary_facts_url": row["primary_facts_url"],
        "private_facts_url": row["private_facts_url"],
        "adaptive_resolver_url": row["adaptive_resolver_url"],
        "ttl": row["ttl_seconds"],
        "issued_at": _now(),
    }
    signed = sign_payload(payload, PRIVATE_KEY)
    return AgentAddr(**signed)


@app.get("/")
def root():
    return {
        "service": "nanda-index",
        "version": "0.1.0",
        "public_key": PUBLIC_KEY,
        "agents_registered": len(db.list_agents()),
    }


@app.post("/register", response_model=AgentAddr)
def register(req: RegisterRequest):
    if db.get_by_name(req.agent_name) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"agent_name '{req.agent_name}' already registered",
        )

    agent_id = f"nanda:{uuid.uuid4()}"
    db.insert_agent(
        agent_id=agent_id,
        agent_name=req.agent_name,
        public_key=req.public_key,
        primary_facts_url=req.primary_facts_url,
        private_facts_url=req.private_facts_url,
        adaptive_resolver_url=req.adaptive_resolver_url,
        ttl_seconds=req.ttl,
        registered_at=_now(),
    )
    return _row_to_agent_addr(db.get_by_name(req.agent_name))


@app.put("/register", response_model=AgentAddr)
def upsert_register(req: RegisterRequest):
    """Idempotent variant — used by the bootstrap script so re-runs work."""
    agent_id = f"nanda:{uuid.uuid4()}"
    existing = db.get_by_name(req.agent_name)
    if existing is not None:
        agent_id = existing["agent_id"]

    db.upsert_agent(
        agent_id=agent_id,
        agent_name=req.agent_name,
        public_key=req.public_key,
        primary_facts_url=req.primary_facts_url,
        private_facts_url=req.private_facts_url,
        adaptive_resolver_url=req.adaptive_resolver_url,
        ttl_seconds=req.ttl,
        registered_at=_now(),
    )
    return _row_to_agent_addr(db.get_by_name(req.agent_name))


@app.get("/resolve/{agent_name:path}", response_model=AgentAddr)
def resolve(agent_name: str):
    row = db.get_by_name(agent_name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no such agent: {agent_name}")
    return _row_to_agent_addr(row)


@app.get("/agents")
def list_agents():
    """Debug/demo aid — not strictly part of the paper's spec."""
    rows = db.list_agents()
    return {
        "count": len(rows),
        "agents": [
            {
                "agent_id": r["agent_id"],
                "agent_name": r["agent_name"],
                "primary_facts_url": r["primary_facts_url"],
                "private_facts_url": r["private_facts_url"],
                "registered_at": r["registered_at"],
            }
            for r in rows
        ],
    }
