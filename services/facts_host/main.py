"""AgentFacts hosting service.

The "metadata distribution tier" from §III/V of the paper. Dumb store —
agents PUT signed AgentFacts here, clients GET them. We deliberately do NOT
verify signatures on PUT; the host has no business knowing which keys are
trusted. That's the client's job.

Two instances of this run in the compose stack:
  - facts-host-primary (:8001) — plays the role of agent-owned hosting
  - facts-host-private (:8002) — plays the role of third-party / PrivateFactsURL
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException


DATA_DIR = Path(os.environ.get("FACTS_HOST_DATA_DIR", "data/facts"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

HOST_NAME = os.environ.get("FACTS_HOST_NAME", "facts-host")

app = FastAPI(
    title=f"NANDA AgentFacts Host ({HOST_NAME})",
    description="Stores and serves signed AgentFacts JSON documents.",
    version="0.1.0",
)


def _path_for(agent_id: str) -> Path:
    safe = agent_id.replace("/", "_").replace(":", "_")
    return DATA_DIR / f"{safe}.json"


@app.get("/")
def root():
    stored = [p.stem for p in DATA_DIR.glob("*.json")]
    return {
        "service": "nanda-facts-host",
        "host_name": HOST_NAME,
        "stored_facts": len(stored),
    }


@app.put("/facts/{agent_id:path}")
def put_facts(agent_id: str, body: dict[str, Any]):
    if "id" not in body or "signature" not in body:
        raise HTTPException(
            status_code=400,
            detail="AgentFacts must include 'id' and 'signature' fields",
        )
    _path_for(agent_id).write_text(json.dumps(body, indent=2))
    return {"stored": agent_id}


@app.get("/facts/{agent_id:path}")
def get_facts(agent_id: str):
    path = _path_for(agent_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"no facts for {agent_id}")
    return json.loads(path.read_text())
