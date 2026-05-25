# EXPLAINER — How this project actually works

> One document that walks through everything in the repo, file by file, with **real JSON captured from a live run** so you can see exactly what every layer produces. Use this to read the code, to defend it in the interview, and to onboard anyone else who looks at the repo.

---

## Table of contents

1. [Project at a glance](#1-project-at-a-glance)
2. [The six services, and what each one does](#2-the-six-services-and-what-each-one-does)
3. [The two client surfaces — CLI and web UI](#3-the-two-client-surfaces--cli-and-web-ui)
4. [A full live trace — one resolve, end to end](#4-a-full-live-trace--one-resolve-end-to-end)
5. [The adaptive routing path — when endpoints move](#5-the-adaptive-routing-path--when-endpoints-move)
6. [The tamper demo — what fails and why](#6-the-tamper-demo--what-fails-and-why)
7. [File-by-file map](#7-file-by-file-map)
8. [How a brand-new agent gets registered](#8-how-a-brand-new-agent-gets-registered)
9. [What rotates, what gets cached, what gets re-verified](#9-what-rotates-what-gets-cached-what-gets-re-verified)
10. [How to run it yourself](#10-how-to-run-it-yourself)

---

## 1. Project at a glance

The job: build a **working prototype of the NANDA paper's three-tier architecture** for the Internet of AI Agents. Replace DNS's "name → IP" lookup with a richer, verifiable, privacy-preserving discovery layer that scales to billions of agents.

What the system actually does, in one sentence:

> *A client looks up an agent by name → gets back a signed pointer → follows the pointer to a signed credential about the agent → verifies both signatures in the browser → optionally asks an adaptive resolver for the best endpoint right now → calls that endpoint.*

What separates this from "just DNS":
- Every signed document **expires by design** (1 hour at the index, 5 min at the metadata, 60 sec at the routing layer)
- Every signature is **independently verifiable** — no need to trust any single server
- The architecture is **a quilt** — different agents can use different hosting models (agent-owned, third-party, neutral) and they all coexist behind the same lookup
- A **tampered document is detected and refused** before the agent is ever called

---

## 2. The six services, and what each one does

When you run `docker compose up`, six FastAPI processes come up. Here's what each one is responsible for and *why it exists as a separate process*.

### 2.1 Index service — port **8000** — `services/index_service/`

**Role:** the lean registry. Maps agent names to signed `AgentAddr` records.

**What it stores:** for each agent, just 7 fields — agent ID, name, public key, two facts URLs, optional resolver URL, TTL. **No skills, no endpoints, no capabilities.** Those live elsewhere. SQLite file at `data/index.sqlite`.

**What it signs:** every `AgentAddr` returned by `GET /resolve/{name}`. The signature is regenerated on every resolve with a fresh `issued_at` timestamp, so the TTL window is anchored to *when you asked*, not when the agent registered.

**Keypair:** auto-generated on first start, persisted to `data/index_keypair.json`. The public key is exposed at `GET /` so any client can fetch it and verify signatures the index produced.

**Also serves:** the entire web UI under `/ui/` — same process, same port. Saves you running a separate web server.

**Why it's a separate service:** because the whole NANDA bet is that the index stays small and stable. Folding metadata or routing logic into it would defeat the purpose — write amplification would crush it at scale.

### 2.2 Facts Host (primary) — port **8001** — `services/facts_host/`

**Role:** stores and serves signed `AgentFacts` documents — the rich, capability-bearing W3C VCs.

**Plays the role of:** the agent's own infrastructure. In real deployments this would be Salesforce serving facts about its translation agent at `https://salesforce.com/.well-known/agent-facts/...`.

**What it doesn't do:** verify signatures on PUT. It's deliberately dumb storage. The client is the verifier — the paper is explicit that hosts shouldn't be the trust anchor.

### 2.3 Facts Host (private) — port **8002** — `services/facts_host/`

**Same code as 2.2**, different env var (`FACTS_HOST_NAME=private`). Stores its facts in a separate folder.

**Plays the role of:** a third-party / neutral facts host — what the paper calls the **privacy path**. If a client looks up an agent via the `private_facts_url` instead of the `primary_facts_url`, the agent's own server never learns the client was interested. Splits "who's asking" from "what was asked."

**Why it's a separate process:** to make the quilt model concrete. Same code template, two roles, demonstrably independent. In production these would be operated by different organizations.

### 2.4 Agent — echo — port **8010** — `services/agents/`

**Role:** a sample agent. `POST /echo` returns whatever you send it. Trivial on purpose — the demo is about *routing and trust*, not about the agent itself doing anything clever.

### 2.5 Agent — translate — port **8011** — `services/agents/`

Same code, different env var (`AGENT_KIND=translate`). `POST /translate` uppercases the input (mock translator). Two agents prove the routing chain works for more than one target.

### 2.6 Adaptive Resolver — port **8020** — `services/adaptive_resolver/`

**Role:** Section VI of the paper. Picks the best endpoint *right now* from a configurable pool, returns a signed routing token.

**Supported policies:**
- `geo` — match `client_region` to endpoint's region tag
- `capability` — match `requested_capability` to endpoint's declared capabilities
- `default` / `load` — round-robin

**What it signs:** every routing token includes the resolver's signature + a 60-second `expires_at`. The client verifies both before calling the endpoint.

**Why it's a separate process:** because routing logic changes faster than identity. Putting it behind its own URL means agents can swap from a round-robin resolver to a geo-aware one without touching the index, and clients can refuse to follow a resolver they don't trust.

---

## 3. The two client surfaces — CLI and web UI

Same backend, two ways to drive it.

### 3.1 The CLI — `nanda/cli.py`

Five commands:

```bash
python -m nanda.cli list                            # show all registered agents
python -m nanda.cli resolve <agent_name>            # walk the chain, verify everything
python -m nanda.cli call    <agent_name> -m "..."   # resolve + verify + POST a message
python -m nanda.cli call    <agent_name> --adaptive --region eu-west
python -m nanda.cli demo-tamper <agent_name>        # prove the verifier rejects mutation
```

Built with **Typer + Rich**. Every signature check is printed step-by-step so a security reviewer can read the trust chain top-to-bottom.

### 3.2 The web UI — `frontend/` (served at `/ui/`)

Single HTML page + one CSS file + one JS file. **No build step, no node_modules.** Tailwind loads from CDN. **TweetNaCl loads from CDN** for in-browser Ed25519 verification — the green ✓ a reviewer sees is verified *client-side*, not a server lying about itself.

UI sections:
- Service health pills (top right) — pings every service every 15 s
- Architecture cards explaining the 3 tiers
- Agent registry with Resolve / Call buttons
- Live cascade panel that animates each verification step
- Call panel with optional adaptive-routing toggle + region picker
- Tamper demo with a side-by-side diff

---

## 4. A full live trace — one resolve, end to end

This is what `python -m nanda.cli resolve urn:agent:demo:echo` actually does, with real bytes captured from a live run.

### Step 1 — `GET /` on the index

The client asks the index for its public key. This is the trust anchor — without it, nothing can be verified.

```http
GET http://127.0.0.1:8000/
```

Response:
```json
{
  "service": "nanda-index",
  "version": "0.1.0",
  "public_key": "KlIi3GVZQZzCclt75RSd76WE/ijHl443RT26An0A6ck=",
  "agents_registered": 3
}
```

The client caches `public_key` for the session.

### Step 2 — `GET /resolve/{name}` → the signed AgentAddr

```http
GET http://127.0.0.1:8000/resolve/urn:agent:demo:echo
```

The index looks up the agent in SQLite, builds a fresh record (with current `issued_at`), signs it with its private key, returns:

```json
{
  "agent_id": "nanda:de556353-294e-4747-a72b-658bb96649fc",
  "agent_name": "urn:agent:demo:echo",
  "public_key": "E1csLuaS2Ek6TlmtxVBRx1qSjzmUcs4fPBB0TBvIs6M=",
  "primary_facts_url": "http://127.0.0.1:8001/facts/nanda:de556353-...",
  "private_facts_url": null,
  "adaptive_resolver_url": null,
  "ttl": 3600,
  "issued_at": "2026-05-25T18:46:13Z",
  "signature": "/Apwgpod5INiJHKFIkM73W5SzFllHDqAcFjPrZQpTZ+QWdERoKiaTCcuSPqNkfGfhSupYHfO20nGZBmZMEq2AQ=="
}
```

Note: this is the entire record. **~500 bytes.** No capabilities, no skills — just pointers + signature.

### Step 3 — Verify the AgentAddr against the index's public key

The client takes the document, removes the `signature` field, runs it through **JCS canonicalization** (RFC 8785 — sorts keys, strips whitespace), and calls `Ed25519.verify(canonical_bytes, signature, index_pubkey)`.

If this fails: the document was tampered with, or the index isn't who it claims. **Abort.**

If it passes: the client now trusts the agent's `public_key` field — because the index vouches for it.

### Step 4 — `GET <primary_facts_url>` → the W3C Verifiable Credential

```http
GET http://127.0.0.1:8001/facts/nanda:de556353-...
```

The facts host returns the agent's signed VC. Real bytes from the live run:

```json
{
  "@context": [
    "https://www.w3.org/ns/credentials/v2",
    "https://w3id.org/security/data-integrity/v2"
  ],
  "type": ["VerifiableCredential", "AgentFactsCredential"],
  "issuer": "key:E1csLuaS2Ek6TlmtxVBRx1qSjzmUcs4fPBB0TBvIs6M=",
  "validFrom": "2026-05-25T18:37:17Z",
  "credentialSubject": {
    "id": "nanda:de556353-294e-4747-a72b-658bb96649fc",
    "agent_name": "urn:agent:demo:echo",
    "label": "Echo Agent",
    "description": "Returns whatever you send it. Useful for testing routing.",
    "version": "0.1.0",
    "provider": { "name": "NANDA Demo", "url": "http://localhost" },
    "endpoints": { "static": ["http://127.0.0.1:18010/echo"] },
    "capabilities": {
      "modalities": ["text"],
      "streaming": false,
      "authentication": { "methods": ["none"] }
    },
    "skills": [
      { "id": "echo", "description": "Echoes the input message back." }
    ],
    "ttl": 300
  },
  "proof": {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "created": "2026-05-25T18:37:17Z",
    "verificationMethod": "key:E1csLuaS2Ek6TlmtxVBRx1qSjzmUcs4fPBB0TBvIs6M=",
    "proofPurpose": "assertionMethod",
    "proofValue": "rIX0mA/AAqT/DSJvt58ml7582IsnSnnN1GdSEuxYjSofEOpuU2M/6+SkB+TxV+xkONu22mZHgOf4YO8c5Xr6Ag=="
  }
}
```

This is a **real W3C Verifiable Credential v2**. Any VC-aware verifier in the world can validate this — not just your code.

- `@context` declares the spec dialect (W3C Credentials v2 + Data Integrity v2)
- `type` says this is both a generic `VerifiableCredential` and the specific `AgentFactsCredential` subtype
- `issuer` and `verificationMethod` both name the agent's public key
- `credentialSubject` holds everything the agent claims about itself
- `proof.cryptosuite` declares `eddsa-jcs-2022` — Ed25519 over JCS-canonical JSON
- `proof.proofValue` is the signature

### Step 5 — Verify the VC against the agent's public key

The client takes the VC, **strips the entire `proof` block**, runs it through JCS canonicalization, and calls `Ed25519.verify(canonical_bytes, proofValue, agent_pubkey)`.

The agent's public key came from the `AgentAddr` we verified in step 3 — so the trust chain is:

```
trust the index pubkey (cached)
  → trust the AgentAddr (signed by index)
    → trust the agent's pubkey inside it
      → trust the VC (signed by agent's pubkey)
        → trust the endpoint URL inside the VC
```

If any link in that chain breaks, the client refuses to use the endpoint.

### Step 6 — POST to the (now-trusted) endpoint

```http
POST http://127.0.0.1:18010/echo
Content-Type: application/json

{ "message": "hello world" }
```

Response:
```json
{ "echo": "hello world" }
```

That's the entire flow. **Six HTTP requests, two signature verifications, one endpoint call.** End to end on a local machine: ~300 ms.

---

## 5. The adaptive routing path — when endpoints move

If the agent has an `adaptive_resolver_url` in its AgentAddr (the `multiregion` demo agent does), the client can skip the static endpoint and ask the resolver for a real-time pick.

### Step 7 — `POST /dispatch` on the resolver

```http
POST http://127.0.0.1:18020/dispatch
Content-Type: application/json

{
  "agent_name": "urn:agent:demo:multiregion",
  "client_region": "eu-west",
  "policy": "geo"
}
```

The resolver looks at its configured pool for `urn:agent:demo:multiregion`:

```json
[
  { "url": "http://...:18010/echo",      "region": "us-east", "capabilities": ["echo"] },
  { "url": "http://...:18011/translate", "region": "eu-west", "capabilities": ["translate"] }
]
```

Picks the eu-west one (geo policy match), signs a routing token:

```json
{
  "agent_name": "urn:agent:demo:multiregion",
  "endpoint": "http://127.0.0.1:18011/translate",
  "region": "eu-west",
  "policy_applied": "geo",
  "issued_at": 1779734774,
  "expires_at": 1779734834,
  "resolver_pubkey": "ilG3z0sdIP6uUe1m7d1kx2QYyd/+CD6KihqvmTrHtP8=",
  "signature": "1J5prvTIwcSf69mMO5kYYTdV5w7NIVrJnt9uy1GrU0bR3pnIL7XQuYMAPqvMJE4ES6xr7BObhumeg+ieswabDw=="
}
```

The client verifies this token's signature against `resolver_pubkey` *before* using `endpoint`. **TTL is 60 seconds** — after that, the client must ask the resolver again.

This is how the paper's promise of "sub-second failover and DDoS shuffle-sharding" gets built in practice: routing decisions are short-lived and signed, not baked into a long-lived DNS cache.

---

## 6. The tamper demo — what fails and why

`python -m nanda.cli demo-tamper urn:agent:demo:echo` does this:

1. Fetches the real AgentAddr (signed by the index) — verifies it. **OK.**
2. Fetches the real AgentFacts VC (signed by the agent) — verifies it. **OK.**
3. Mutates one field inside the VC: changes `credentialSubject.endpoints.static[0]` from `http://127.0.0.1:18010/echo` to `http://evil.example.com/steal`.
4. Re-runs the verifier on the mutated VC.

The verifier:
- Strips the `proof` block (which still contains the *original* signature, because the attacker doesn't have the agent's private key to make a new one)
- Re-canonicalizes the mutated `credentialSubject`
- Calls `Ed25519.verify(new_canonical_bytes, original_signature, agent_pubkey)`

The signature was computed over different bytes (the original document). The new bytes don't match. **Verification fails. Client refuses to call `evil.example.com`.**

Why this works: Ed25519 has the property that signatures are bound to specific bytes. An attacker who can see and modify documents in flight still cannot forge a new signature without the private key. JCS canonicalization removes the "different whitespace = different bytes" attack surface, so there's no way to mutate the JSON while preserving the original bytes.

This is the entire security argument of the paper, demonstrated in one click in the browser.

---

## 7. File-by-file map

```
projectNanda/
├── nanda/                       # shared Python library
│   ├── __init__.py
│   ├── crypto.py                # ★ Ed25519 sign/verify + W3C VC envelope
│   ├── schemas.py               # Pydantic models for AgentAddr, AgentFactsVC
│   └── cli.py                   # ★ client CLI (resolve / call / demo-tamper)
│
├── services/
│   ├── index_service/
│   │   ├── main.py              # FastAPI: /, /register, /resolve, /agents
│   │   └── db.py                # SQLite layer (one table, ~70 LOC)
│   ├── facts_host/
│   │   └── main.py              # FastAPI: PUT/GET /facts/{id}, accepts VC payload
│   ├── agents/
│   │   └── main.py              # FastAPI: /echo, /translate (env-var routed)
│   └── adaptive_resolver/
│       └── main.py              # ★ FastAPI: POST /dispatch → signed routing token
│
├── frontend/                    # web UI, no build step
│   ├── index.html               # layout, sections, sticky header
│   ├── styles.css               # custom CSS + Tailwind @apply block
│   ├── app.js                   # ★ in-browser VC verifier, cascade, tamper, adaptive
│   └── config.js                # service URLs (override via query string)
│
├── scripts/
│   └── bootstrap.py             # ★ registers 3 demo agents end-to-end
│
├── tests/
│   └── test_crypto.py           # 7 unit tests: sign/verify/VC/tamper/canonical
│
├── .github/workflows/
│   └── ci.yml                   # pytest + integration smoke + ruff lint
│
├── docs/                        # README screenshots (auto-captured)
│
├── docker-compose.yml           # one-command 6-service stack
├── Dockerfile                   # single Python image, all services use it
├── fly.toml                     # Fly.io deploy config for the index + UI
├── requirements.txt             # 7 Python deps
│
└── docs/                        # markdown for humans
    ├── README.md                # quickstart + screenshots + paper alignment
    ├── PLAN.md                  # build plan, scope decisions, explicit non-goals
    ├── ROADMAP.md               # first 90 days as VP of Engineering
    ├── DEMO_GUIDE.md            # interview/demo script + Q&A prep
    ├── VIDEO_SCRIPT.md          # pre-interview video script + production guide
    └── EXPLAINER.md             # ← you are here
```

The five ★ files are the load-bearing code. Everything else is glue, ops, or docs. Total Python: under 1000 LOC excluding tests.

### The core function in `nanda/crypto.py`

If you read only one piece of code in the repo, read these two functions:

```python
def sign_vc_payload(*, credential_subject, issuer_public_key_b64, issuer_private_key_b64,
                    credential_type="AgentFactsCredential"):
    issued_at = _now_iso()
    credential = {
        "@context": [VC_V2_CONTEXT, DATA_INTEGRITY_CONTEXT],
        "type": ["VerifiableCredential", credential_type],
        "issuer": f"key:{issuer_public_key_b64}",
        "validFrom": issued_at,
        "credentialSubject": credential_subject,
    }
    sk = signing.SigningKey(_b64d(issuer_private_key_b64))
    sig = sk.sign(canonicalize(credential)).signature   # ← THE signature line
    credential["proof"] = {
        "type": "DataIntegrityProof",
        "cryptosuite": CRYPTOSUITE,                     # "eddsa-jcs-2022"
        "created": issued_at,
        "verificationMethod": f"key:{issuer_public_key_b64}",
        "proofPurpose": "assertionMethod",
        "proofValue": _b64e(sig),
    }
    return credential


def verify_vc(credential, public_key_b64):
    proof = credential.get("proof")
    if not proof or proof.get("cryptosuite") != CRYPTOSUITE:
        return False
    proof_value = proof.get("proofValue")
    if not proof_value:
        return False
    unsigned = {k: v for k, v in credential.items() if k != "proof"}   # strip proof
    try:
        vk = signing.VerifyKey(_b64d(public_key_b64))
        vk.verify(canonicalize(unsigned), _b64d(proof_value))           # ← THE verify line
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False
```

That's it. Two functions, ~30 lines. Everything else in the system is plumbing around these.

### The matching JS in `frontend/app.js`

```javascript
function verifyVC(credential, publicKeyB64) {
  const proof = credential?.proof;
  if (!proof || proof.cryptosuite !== "eddsa-jcs-2022" || !proof.proofValue) {
    return false;
  }
  const { proof: _omit, ...unsigned } = credential;
  try {
    const msg = new TextEncoder().encode(canonicalize(unsigned));
    const sig = nacl.util.decodeBase64(proof.proofValue);
    const pub = nacl.util.decodeBase64(publicKeyB64);
    return nacl.sign.detached.verify(msg, sig, pub);
  } catch (e) { return false; }
}
```

Same logic, in JavaScript, runs in the browser. Same cryptosuite. Same canonicalization. Same answer.

The fact that the Python sign and the JavaScript verify produce identical results across language boundaries is the *whole point* of JCS + Ed25519. That's why the cryptosuite is called `eddsa-jcs-2022` — it's the interop guarantee.

---

## 8. How a brand-new agent gets registered

`scripts/bootstrap.py` does this for every demo agent. The flow:

1. **Generate an Ed25519 keypair for the agent.** Persisted to `data/agent_keys/<safe_name>.json`.

2. **Register with the index.** Send `PUT /register` with `agent_name`, the new `public_key`, `primary_facts_url` (where the facts WILL be hosted), optional `private_facts_url`, optional `adaptive_resolver_url`, TTL.

   The index assigns a UUID (`agent_id`), stores the row in SQLite, and returns the signed AgentAddr.

3. **Build the AgentFacts subject** — a dict with id, label, description, endpoints, capabilities, skills.

4. **Sign it as a W3C VC** using the agent's private key. The cryptosuite is `eddsa-jcs-2022`. Result: a full VC with `proof.proofValue`.

5. **PUT the signed VC to the facts host.** The host doesn't verify — it just stores it. (The client will verify when it fetches.)

6. **Done.** The agent is now resolvable: `nanda.cli list` will show it.

For the third demo agent (`multiregion`), one extra step:
- `adaptive_resolver_url` is set in the registration body, pointing at the adaptive resolver's `/dispatch` endpoint.
- The resolver has a pre-configured pool for that agent (set via the `ADAPTIVE_POOLS` env var in `docker-compose.yml`).

---

## 9. What rotates, what gets cached, what gets re-verified

| Layer | TTL | What happens at expiry |
|---|---|---|
| Index public key | session (cached forever in practice) | Client refetches at start of session |
| `AgentAddr` | 3600 s (1 hour) | Client must re-resolve; new `issued_at`, new signature |
| `AgentFacts` VC | 300 s (5 min) | Client must re-fetch from facts host |
| Adaptive routing token | 60 s | Client must re-dispatch |

**The pattern:** every layer's freshness is shorter than the layer above it. The index changes least often (identity is stable). The facts change moderately often (capabilities evolve). The routing token changes constantly (load shifts every second).

This means a leaked routing token is worthless in a minute. A leaked AgentFacts is stale in 5 minutes. Even if the worst happens and an agent's *private key* leaks, the damage window is bounded — the agent re-registers with a new key, the index points to the new key, all previously-signed facts become unverifiable against the current pubkey.

Compare to a leaked TLS certificate in DNS-land, which can be trusted in browser caches for *hours to days*.

---

## 10. How to run it yourself

### With Docker (recommended)

```bash
cd projectNanda
docker compose up --build -d              # 6 services
pip install -r requirements.txt           # for the CLI + bootstrap
python scripts/bootstrap.py               # registers 3 demo agents
```

Then either open `http://localhost:8000/ui/` in a browser, or run CLI commands:

```bash
python -m nanda.cli list
python -m nanda.cli resolve urn:agent:demo:echo
python -m nanda.cli call urn:agent:demo:echo --message "hello"
python -m nanda.cli call urn:agent:demo:multiregion --adaptive --region eu-west
python -m nanda.cli demo-tamper urn:agent:demo:echo
```

### Without Docker

Each service is a `uvicorn` command — see `command:` blocks in `docker-compose.yml`. Run each in its own terminal, pointing at distinct ports. The MVP is intentionally easy to dissect this way.

### If your port 8000 is busy

Run on alt ports (e.g. `18000`–`18020`) and tell the UI where to find them via query params:

```
http://localhost:18000/ui/?index=http://localhost:18000&facts1=http://localhost:18001&facts2=http://localhost:18002&agent1=http://localhost:18010&agent2=http://localhost:18011&resolver=http://localhost:18020
```

The frontend's `config.js` honors these overrides at runtime — no rebuild needed.

### To stop everything

```bash
docker compose down
rm -rf data/         # wipes registered agents + generated keypairs
```

---

## A short reading order

If someone new is trying to understand the project from cold, send them through the docs in this order:

1. **`README.md`** — what it does, screenshots, quickstart
2. **`EXPLAINER.md`** (this file) — how every piece works
3. **`PLAN.md`** — what was deliberately cut and why
4. **`nanda/crypto.py`** — the two functions that anchor the trust model
5. **`frontend/app.js`** — same logic in JavaScript, in the browser
6. **`ROADMAP.md`** — where this would go in the next 90 days

That's enough to ask intelligent questions about the architecture.
