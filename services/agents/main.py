"""Sample agent endpoints.

Two trivial agents the client can actually call once it has resolved them.
Real agents would do real work; these prove the resolution chain reaches a
live endpoint.

Configured via env var AGENT_KIND={"echo","translate"} so we can run the
same image as either agent in docker-compose.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI


AGENT_KIND = os.environ.get("AGENT_KIND", "echo")
AGENT_LABEL = os.environ.get("AGENT_LABEL", AGENT_KIND.title() + " Agent")

app = FastAPI(title=f"NANDA Sample Agent ({AGENT_LABEL})", version="0.1.0")


@app.get("/")
def root():
    return {"agent_kind": AGENT_KIND, "label": AGENT_LABEL}


@app.post("/echo")
def echo(body: dict[str, Any]):
    return {"echo": body.get("message", body)}


@app.post("/translate")
def translate(body: dict[str, Any]):
    text = str(body.get("message", ""))
    target = body.get("target_lang", "EN")
    return {
        "translated": text.upper(),
        "target_lang": target,
        "note": "mock translator — uppercases input. Replace with a real model later.",
    }
