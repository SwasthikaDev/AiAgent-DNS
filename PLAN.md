# NANDA MVP — Build Plan

A minimum-cost, runnable prototype of the NANDA Index architecture described in *Beyond DNS: Unlocking the Internet of AI Agents via the NANDA Index and Verified AgentFacts*.

This plan is the contract for what gets built and what gets deferred.

---

## 1. What the paper asks for vs. what the MVP delivers

The paper describes a 3-layer stack:

1. **Lean Index** — minimal record (`AgentAddr`) mapping `agent_name` → pointers + signature.
2. **AgentFacts** — rich, signed JSON-LD document with capabilities, endpoints, credentials.
3. **Dynamic Resolution** — adaptive resolver, TTL-scoped endpoint lists, geo-LB.

The challenge brief (Level 1) asks for:

- A working **client → index → AgentAddr → AgentFacts → endpoint** flow.
- **≥ 2 agents** registered and resolvable.
- **Verifiable** metadata — client must be able to detect tampering.

The MVP therefore implements **layers 1 and 2 fully**, and **stubs layer 3** (we ship static endpoints; the schema field for `adaptive_resolver_url` exists but is not implemented as a separate service). This keeps scope honest for a 2-day build and matches "functional is the bar, not polished" in the brief.

### Level 2 stretch (only if time permits)

- A **second registration type** (third-party-hosted `private_facts_url` via a separate facts host) — demonstrates the "quilt" model with one NANDA-native agent and one enterprise-style hosted agent.
- A **CLI tool** (`nanda` command) that walks the full chain with `--verbose` output, so reviewers can see every signature check.
- A **tamper-detection demo** — one command that mutates a signed document and shows the client rejecting it.

---

## 2. Architecture decisions

### 2.1 Stack — chosen for zero-cost local run

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.11** | Fast to write, broad crypto support, reviewer can read it. |
| Web framework | **FastAPI** | Async, auto-generates OpenAPI docs (free reviewer-friendly UI at `/docs`). |
| Crypto | **PyNaCl** (libsodium binding) | Ed25519 is what the paper specifies. PyNaCl is the established library — no hand-rolled primitives. |
| Storage | **SQLite** | Zero infra, file-based, perfect for an MVP. No DB server to run. |
| Process orchestration | **docker-compose** | One `docker compose up` runs the whole system. Reviewer doesn't need Python installed. |
| Client | **Python CLI** using `httpx` + `typer` | Same language as services; one venv covers both. |
| Frontend | **None for Level 1.** Optional minimal HTML page served by index for Level 2. | A web UI adds days of work for marginal demo value. CLI with colored output is more honest about what the system actually does. |
| Deployment | **Local only.** No cloud spend. | Brief explicitly allows `docker-compose up` as the runnable artifact. |

### 2.2 Service topology

Four processes, one repo:

```
┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐
│              │      │                  │      │                  │
│  Client CLI  │─────▶│  Index Service   │      │  Facts Host A    │
│              │      │  :8000           │      │  (agent-owned)   │
└──────┬───────┘      │                  │      │  :8001           │
       │              │  - register      │      │                  │
       │              │  - resolve       │      └──────────────────┘
       │              │  - sign AgentAddr│      ┌──────────────────┐
       │              │  - SQLite        │      │                  │
       │              └──────────────────┘      │  Facts Host B    │
       │                                        │  (3rd-party,     │
       │                                        │  private path)   │
       │                                        │  :8002           │
       │                                        └──────────────────┘
       │              ┌──────────────────┐
       └─────────────▶│  Agent Endpoint  │
                      │  :8010, :8011    │
                      │  (echo, translate)│
                      └──────────────────┘
```

- **Index service** (port 8000): the lean registry. Holds public keys + signed `AgentAddr` records.
- **Primary facts host** (port 8001): serves `AgentFacts` for the "agent-owned" agent.
- **Private facts host** (port 8002): serves `AgentFacts` for the "third-party-hosted" agent — demonstrates `private_facts_url` path from §VII of the paper.
- **Agent endpoints** (ports 8010, 8011): the actual agents the client calls after resolving. Trivial — one echo, one mock-translate.
- **Client CLI**: walks the chain.

Splitting facts hosts into two separate services is deliberate — it makes the "quilt" idea concrete instead of theoretical, and it's cheap (same Python process template, different config).

### 2.3 Trust model — what gets signed and by whom

Three signing keys in play (all Ed25519):

| Key | Holder | Signs | Verified by |
|---|---|---|---|
| `K_index` | Index service | `AgentAddr` records | Client (uses index's published public key) |
| `K_agent` | Each agent | Its own `AgentFacts` document | Client (uses agent's `public_key` from the `AgentAddr`) |
| `K_issuer` (deferred) | Credential issuer | Capability claims inside `AgentFacts` (W3C VC) | Client — **deferred to Level 2** as a stub field; full VC chain is overkill for MVP |

Verification chain at the client:

```
1. Fetch index_public_key (one-time, cached).
2. Resolve agent_name → AgentAddr. Verify sig with K_index.
3. Extract agent's public_key from AgentAddr.
4. Fetch AgentFacts from primary_facts_url (or private_facts_url).
5. Verify AgentFacts sig with the agent's public_key from step 3.
6. Use endpoint from AgentFacts to call the agent.
```

This is **two signatures, two verifications** — enough to demonstrate end-to-end tamper detection without dragging in the full W3C VC stack (which would add days of JSON-LD context wrangling for the same demo outcome).

### 2.4 Why not full W3C Verifiable Credentials?

The paper specifies W3C VC v2 for `AgentFacts`. For an MVP, the *outcome* of VCs — "client can detect tampering and untrusted issuers" — is what matters for the brief ("the client should be able to detect tampering"). The brief explicitly says **"signed JSON, W3C Verifiable Credentials, or another approach of your choice"**.

We use **detached Ed25519 signatures over canonical JSON** (RFC 8785 JCS). This is:

- The same crypto primitive VCs use.
- Standards-based (JCS is an RFC, not a snowflake).
- Implementable in ~30 lines vs. ~300 for full VC + JSON-LD.
- Honest about what we're shipping — README will call this out as a "VC-shaped" signature, not actual VCs.

If a reviewer wants real VCs, the upgrade path is a wrapper around the same signature — schema stays the same.

---

## 3. Data model

### 3.1 SQLite schema (in the index service)

```sql
CREATE TABLE agents (
  agent_id              TEXT PRIMARY KEY,           -- e.g. "nanda:550e8400-..."
  agent_name            TEXT UNIQUE NOT NULL,       -- e.g. "urn:agent:demo:echo"
  public_key            TEXT NOT NULL,              -- base64 Ed25519 public key
  primary_facts_url     TEXT NOT NULL,
  private_facts_url     TEXT,                       -- nullable
  adaptive_resolver_url TEXT,                       -- nullable, stub for now
  ttl_seconds           INTEGER NOT NULL DEFAULT 3600,
  registered_at         TEXT NOT NULL               -- ISO-8601
);
```

Deliberately flat. No migrations framework — for an MVP, a single `CREATE TABLE IF NOT EXISTS` on startup is enough.

### 3.2 `AgentAddr` (returned by index resolve)

```json
{
  "agent_id": "nanda:550e8400-e29b-41d4-a716-446655440000",
  "agent_name": "urn:agent:demo:echo",
  "public_key": "<base64 Ed25519>",
  "primary_facts_url": "http://localhost:8001/facts/nanda:550e...",
  "private_facts_url": null,
  "adaptive_resolver_url": null,
  "ttl": 3600,
  "issued_at": "2026-05-25T10:00:00Z",
  "signature": "<base64 Ed25519 sig over the above fields, JCS-canonicalized>"
}
```

### 3.3 `AgentFacts` (returned by facts host)

A trimmed version of the paper's Appendix schema — only the fields needed to demo the flow:

```json
{
  "id": "nanda:550e8400-...",
  "agent_name": "urn:agent:demo:echo",
  "label": "Echo Agent",
  "description": "Returns whatever you send it.",
  "version": "0.1.0",
  "provider": { "name": "NANDA Demo", "url": "http://localhost:8001" },
  "endpoints": {
    "static": ["http://localhost:8010/echo"]
  },
  "capabilities": {
    "modalities": ["text"],
    "streaming": false,
    "authentication": { "methods": ["none"] }
  },
  "skills": [
    { "id": "echo", "description": "Echoes input back as output." }
  ],
  "ttl": 300,
  "issued_at": "2026-05-25T10:00:00Z",
  "signature": "<base64 Ed25519 sig by agent's K_agent over the above>"
}
```

Fields like `evaluations`, `telemetry`, `certification` from the paper's full schema are **omitted from the MVP** — they're nice-to-have but don't change the demo. Schema is extensible: adding them later doesn't break clients.

---

## 4. APIs

### Index service (`:8000`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Health + index public key (so clients can verify AgentAddr sigs). |
| `POST` | `/register` | Register an agent. Body: agent_name, public_key, facts URLs, ttl. Returns the signed AgentAddr. |
| `GET` | `/resolve/{agent_name}` | Returns signed `AgentAddr` for the given name. The primary lookup the client uses. |
| `GET` | `/agents` | Lists registered agents (debug/demo aid — not part of the paper but useful for the reviewer). |

### Facts host (`:8001`, `:8002`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Health. |
| `PUT` | `/facts/{agent_id}` | Publish a signed AgentFacts document. |
| `GET` | `/facts/{agent_id}` | Fetch the signed AgentFacts document. |

### Agent endpoints (`:8010`, `:8011`)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/echo` | Returns the request body verbatim. |
| `POST` | `/translate` | Mock translate — uppercases the input and labels it "translated". |

---

## 5. Client CLI flow

```
$ nanda resolve urn:agent:demo:echo

[1/5] Fetching index public key from http://localhost:8000 ... OK
[2/5] Resolving urn:agent:demo:echo via index ... OK
      AgentAddr signature: VALID (signed by index)
[3/5] Fetching AgentFacts from http://localhost:8001/facts/nanda:550e... ... OK
[4/5] Verifying AgentFacts signature with agent's public key ... VALID
[5/5] Endpoint: http://localhost:8010/echo
      TTL: 300s (expires 2026-05-25T10:05:00Z)
      Capabilities: text, echo

$ nanda call urn:agent:demo:echo --message "hello"
{"echo": "hello"}

$ nanda demo-tamper urn:agent:demo:echo
Simulating a tampered AgentFacts (mutating 'endpoints.static[0]')...
[4/5] Verifying AgentFacts signature ... INVALID — REJECTED
Client refused to use the tampered endpoint. Good.
```

The `demo-tamper` subcommand is the explicit proof for the brief's "client should be able to detect tampering" requirement.

---

## 6. Implementation phases

Each phase ends with a committable, runnable state. Commits stay small to preserve a meaningful history (brief: "please do not squash").

### Phase 0 — Scaffold (30 min)
- Repo layout, `.gitignore`, `requirements.txt`, `docker-compose.yml` skeleton.
- Commit: "scaffold project structure"

### Phase 1 — Crypto + storage primitives (1 hr)
- `nanda/crypto.py`: keygen, sign, verify, JCS canonicalization.
- Unit-test signing round-trip in a small `tests/` file.
- Commit: "ed25519 sign/verify with JCS canonicalization"

### Phase 2 — Index service (1.5 hr)
- FastAPI app, SQLite init, `/register`, `/resolve`, `/agents`, `/`.
- Bootstrap: generate index keypair on first run, persist to disk.
- Commit: "index service with signed AgentAddr"

### Phase 3 — Facts host (1 hr)
- FastAPI app, in-memory dict for stored facts (no DB needed — facts hosts are dumb stores).
- `PUT`/`GET /facts/{id}`.
- Commit: "facts host with signed AgentFacts storage"

### Phase 4 — Agent endpoints (30 min)
- One FastAPI app, two routes (`/echo`, `/translate`).
- Commit: "sample agents (echo, translate)"

### Phase 5 — Bootstrap script (1 hr)
- `scripts/bootstrap.py`: generates two agent keypairs, registers both with the index, publishes their AgentFacts to the right hosts.
- One agent uses primary host (8001), the other uses private host (8002) — demonstrates the quilt.
- Commit: "bootstrap script registers two demo agents"

### Phase 6 — Client CLI (2 hr)
- `nanda/cli.py` using typer + httpx.
- Commands: `resolve`, `call`, `demo-tamper`.
- Colored output via `rich` (one dep, big readability win).
- Commit: "client CLI with resolve, call, demo-tamper"

### Phase 7 — docker-compose + README (1 hr)
- One Dockerfile, compose file spinning up all 4 services.
- README with prereqs, quickstart, architecture diagram (ASCII), notes on AI-tool usage.
- Commit: "docker-compose + README"

### Phase 8 — Polish (remaining time)
- Better error messages.
- `/agents` listing in the index.
- Maybe a tiny `nanda doctor` command that pings every service.

**Total: ~9 hours of focused work, fits in 2 days with margin.**

---

## 7. Repo layout

```
projectNanda/
├── README.md
├── PLAN.md                    (this file)
├── details.md                 (the brief)
├── beyondDNS.pdf
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .gitignore
├── nanda/
│   ├── __init__.py
│   ├── crypto.py              (sign/verify/JCS)
│   ├── schemas.py             (Pydantic models for AgentAddr, AgentFacts)
│   └── cli.py                 (client CLI entrypoint)
├── services/
│   ├── index_service/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── db.py
│   ├── facts_host/
│   │   ├── __init__.py
│   │   └── main.py
│   └── agents/
│       ├── __init__.py
│       └── main.py
├── scripts/
│   └── bootstrap.py
├── tests/
│   └── test_crypto.py
└── data/                      (gitignored — SQLite file, keys live here)
```

---

## 8. Cost summary

| Item | Cost |
|---|---|
| Hosting | $0 — runs locally via docker-compose |
| Domain / DNS | $0 — uses localhost |
| Database | $0 — SQLite file |
| TLS certs | $0 — HTTP for local demo (paper's cryptographic guarantees don't depend on TLS; they're at the application layer) |
| AI coding tools | Already paid for (Claude) |
| **Total** | **$0** |

If a reviewer wants to see it running without installing anything, a Loom under 5 min covers that — also free.

---

## 9. Explicit non-goals for the MVP

So we don't accidentally try to build them:

- ❌ Cloud deployment (free tier or otherwise)
- ❌ Real W3C Verifiable Credentials (we ship JCS+Ed25519, schema-compatible)
- ❌ IPFS or any decentralized storage (private_facts_url points to a second HTTP host instead)
- ❌ Tor / mix-net for the privacy path (it's about hosting decoupling, not network anonymity)
- ❌ DID resolution (`did:web`, `did:key` etc.) — agent_name is a plain URN
- ❌ Real revocation lists / VC-Status — TTL expiry is our only freshness mechanism
- ❌ Adaptive resolver microservice — schema field exists, no implementation
- ❌ Web frontend — CLI only
- ❌ Authentication on the index `/register` endpoint — anyone can register; fine for a demo, called out in README

Each of these is a real feature in the paper. Each is the right thing to build *next*. None are needed to satisfy Level 1 of the brief.
