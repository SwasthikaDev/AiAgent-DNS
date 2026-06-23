"""Standalone NANDA demo agent — run this on the SECOND laptop.

It has zero dependency on the rest of the repo: it's just the trivial endpoint
the client calls *after* it has verified the (locally-signed) AgentFacts. No
keys, no signing here — laptop 1 signs the facts; this only echoes.

Copy just this one file to the other laptop, then:

    pip install fastapi "uvicorn[standard]"
    python remote_agent.py                 # serves on 0.0.0.0:9000

Bind is 0.0.0.0 so it's reachable from the main laptop over the LAN. The
response includes this machine's hostname, so you can *prove* it ran on the
other laptop.
"""

from __future__ import annotations

import os
import socket
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

HOSTNAME = socket.gethostname()

app = FastAPI(title=f"NANDA Remote Demo Agent ({HOSTNAME})", version="0.1.0")

# CORS so the browser UI on the other laptop can call this directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"agent": "remote-echo", "served_by": HOSTNAME}


@app.post("/echo")
def echo(body: dict[str, Any]):
    # served_by proves the call reached THIS machine, not localhost.
    return {"echo": body.get("message", body), "served_by": HOSTNAME}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "9000"))
    print(f"Remote agent '{HOSTNAME}' listening on 0.0.0.0:{port}")
    print("Register it on the main laptop with this machine's LAN IP, e.g.")
    print(f"  python scripts/register_remote_agent.py http://<this-ip>:{port}/echo")
    uvicorn.run(app, host="0.0.0.0", port=port)
