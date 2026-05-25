# NANDA Index MVP

A working prototype of the architecture from *Beyond DNS: Unlocking the Internet of AI Agents via the NANDA Index and Verified AgentFacts* ([paper](https://arxiv.org/pdf/2507.14263)).

A client resolves an agent by name, fetches a signed `AgentAddr` from a lean index, follows it to a signed `AgentFacts` document, verifies every signature, and then calls the agent. If anyone tampers with the metadata in flight, the client refuses to use it.

Ships with **two interfaces** on top of the same backend:

- a **web UI** at `http://localhost:8000/ui/` — the visual demo
- a **CLI** (`python -m nanda.cli`) — the technical surface

> **Going into an interview?** Read [`DEMO_GUIDE.md`](./DEMO_GUIDE.md) first — it has the 90-second script, prepared answers to likely questions, and recovery moves for live failures.

Built for the NANDA VP-of-Engineering technical challenge. See [`PLAN.md`](./PLAN.md) for the build plan and explicit non-goals.

![Landing page](docs/demo-01-landing.png)

---

## Quickstart

You need **Docker** (with `docker compose`) and **Python 3.11+**.

```bash
# 1. Start the five-service stack
docker compose up --build -d

# 2. Install the Python deps (used by the CLI + bootstrap script)
pip install -r requirements.txt

# 3. Register two demo agents
python scripts/bootstrap.py
```

Then either:

**Open the web UI** — recommended for the demo:
```
http://localhost:8000/ui/
```
Click "Resolve" on any agent to watch the trust chain animate in. Click "Run attack" in the Tamper Detection section to see the client reject a mutated document.

**Or drive it from the CLI** — better for showing internals:
```bash
python -m nanda.cli list
python -m nanda.cli resolve urn:agent:demo:echo
python -m nanda.cli call urn:agent:demo:echo --message "hello"
python -m nanda.cli demo-tamper urn:agent:demo:echo
```

Tear down:

```bash
docker compose down
rm -rf data/
```

If you don't want Docker, you can run each service directly with `uvicorn` — see the `command:` lines in [`docker-compose.yml`](./docker-compose.yml).
If a port is already in use locally, run the stack on alternate ports and open the UI with overrides:
`http://localhost:18000/ui/?index=http://localhost:18000&facts1=http://localhost:18001&facts2=http://localhost:18002&agent1=http://localhost:18010&agent2=http://localhost:18011`

---

## What it looks like

### Resolution cascade (web UI)
Every step is a real HTTP fetch and a real Ed25519 signature check, in the browser via TweetNaCl. The green ✓ is not a server saying "trust me, valid" — it's verified client-side.

![Resolution cascade](docs/demo-02-cascade.png)

### Tamper detection
The client refuses to call an endpoint whose signed document was mutated in flight. Same Ed25519 primitive in the browser.

![Tamper detection](docs/demo-03-tamper.png)

### Calling an agent
After both signatures verify, the client POSTs the message to the endpoint listed in the (now-trusted) AgentFacts.

![Calling an agent](docs/demo-04-call.png)

### CLI output

`python -m nanda.cli resolve urn:agent:demo:echo` prints:

```
[1/5] Fetching index public key from http://localhost:8000
        ✔ index pubkey: AKj9...
[2/5] Resolving 'urn:agent:demo:echo' at the index
        ✔ got AgentAddr (agent_id=nanda:550e...)
[3/5] Verifying AgentAddr signature against the index public key
        ✔ AgentAddr signature VALID
[4/5] Fetching AgentFacts from http://localhost:8001/facts/nanda:550e...
        ✔ got AgentFacts (label='Echo Agent')
[5/5] Verifying AgentFacts signature against the agent's public key (from AgentAddr)
        ✔ AgentFacts signature VALID

╭───────── Resolved agent ──────────╮
│  Label        Echo Agent          │
│  Description  Returns whatever... │
│  Endpoint     http://.../echo     │
│  Skills       echo                │
╰───────────────────────────────────╯
```

`demo-tamper` runs the same chain but mutates the endpoint URL inside the signed `AgentFacts` document, then re-runs the verifier. The signature check fails, and the client refuses to call the rerouted (potentially malicious) endpoint.

---

## What's running

| Port  | Service           | Role |
|-------|-------------------|---|
| 8000  | `index`           | Lean NANDA index. Signs `AgentAddr` records. Also serves the web UI at `/ui/`. |
| 8001  | `facts-primary`   | "Agent-owned" facts hosting → `primary_facts_url`. |
| 8002  | `facts-private`   | Third-party facts hosting → `private_facts_url` (privacy path from §VII). |
| 8010  | `agent-echo`      | Sample agent — echoes input. |
| 8011  | `agent-translate` | Sample agent — mock translator. |

Every service exposes `/` for health and `/docs` for an interactive OpenAPI UI (FastAPI default).

Two agents are registered by `bootstrap.py`:

- `urn:agent:demo:echo` — facts hosted on `facts-primary` (agent-owned model).
- `urn:agent:demo:translate` — facts hosted on `facts-private` (third-party model, demonstrates the quilt registration types from Table 1 of the paper).

---

## How verification works

Two keypairs are involved per request:

1. **Index keypair** (`data/index_keypair.json`, auto-generated on first start). Signs every `AgentAddr` returned by `/resolve`.
2. **Agent keypair** (`data/agent_keys/*.json`, generated by `bootstrap.py`). Signs the agent's own `AgentFacts`.

Verification chain at the client:

```
client ──GET /──▶  index pubkey
client ──GET /resolve/{name}──▶  AgentAddr  ──verify with index pubkey
                                    │
                                    └─ contains agent's public_key
                                    │
client ──GET primary_facts_url──▶  AgentFacts  ──verify with agent's pubkey
                                    │
                                    └─ contains endpoint
client ──POST──▶  endpoint
```

Both signatures use **Ed25519 over RFC 8785-canonicalized JSON**, via [PyNaCl](https://pynacl.readthedocs.io/) (libsodium). No hand-rolled crypto.

### Why not full W3C Verifiable Credentials?

The brief explicitly allows "signed JSON, W3C Verifiable Credentials, or another approach of your choice." VCs use the same Ed25519 primitive plus a JSON-LD envelope. For an MVP demonstrating the resolution flow and tamper detection, the envelope adds friction without changing what the reviewer sees. The signature scheme is VC-compatible — wrapping it in a `proof` block later is a few lines.

---

## Repository tour

```
nanda/                Shared library (crypto, schemas, CLI)
├── crypto.py         Ed25519 + JCS canonical JSON
├── schemas.py        Pydantic models for AgentAddr, AgentFacts
└── cli.py            Client (resolve, call, demo-tamper, list)

services/
├── index_service/    FastAPI app + SQLite for the lean index; serves /ui/
├── facts_host/       FastAPI app that stores + serves signed AgentFacts
└── agents/           Two sample agent endpoints (one process, two roles)

frontend/             Web UI (no build step, no node_modules)
├── index.html        Layout, Tailwind via CDN
├── app.js            Verifier (TweetNaCl) + cascade + tamper demo
├── styles.css        Custom CSS the CDN can't generate
└── config.js         Endpoint URLs (overridable via query params)

scripts/bootstrap.py  Registers the two demo agents end-to-end

tests/test_crypto.py  Sign/verify/tamper-detection unit tests

docs/                 Screenshots used in this README
DEMO_GUIDE.md         Interview/demo script + Q&A prep
PLAN.md               Build plan with explicit non-goals
```

---

## Scope: what's in, what's out

In:

- Lean index (§IV of the paper) with signed `AgentAddr`
- `AgentFacts` schema (§V + Appendix, MVP-trimmed) with detached Ed25519 sigs
- Two registration styles — primary-hosted and third-party-hosted facts (the "quilt")
- Client that walks the chain and verifies both signatures
- Tamper detection demo
- Two live agents the client can actually call

Out (deliberately — see [`PLAN.md`](./PLAN.md) §9):

- Cloud deployment — local docker-compose only (zero hosting cost)
- Real W3C Verifiable Credentials — JCS+Ed25519 stand-in, schema-compatible
- IPFS / Tor — private facts host is a second HTTP service instead
- DID resolution
- Revocation lists / VC-Status
- Adaptive resolver microservice (schema field exists, no implementation)
- Authentication on `/register`

---

## Next steps (post-MVP)

1. Wrap the existing signatures in a W3C VC v2 envelope so the on-the-wire format matches the paper exactly.
2. Add a real `adaptive_resolver` service that does geo or load-aware dispatch.
3. Add a `nanda doctor` CLI command that smoke-tests every service.
4. Stand up a free-tier Fly.io / Railway deployment so reviewers can hit a live URL.

---

## AI tool usage

This MVP was built with Claude (Anthropic) as a pair-programmer over the course of the challenge. Used for:

- Sketching the architecture (which layers to ship vs. defer, given the 2-day window)
- Drafting service skeletons, then iterating on them locally
- Writing the README and `PLAN.md`

Every line was reviewed and the system was run end-to-end before commit.
