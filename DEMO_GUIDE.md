# DEMO GUIDE — How to walk an interviewer through this project

> This is the one document to read before the interview. It is written to be **rehearsable** — short scripts you can deliver verbatim, plus the reasoning to fall back on when a question goes sideways. Read it twice, run the demo once, you're ready.

---

## TL;DR — the 30-second pitch

> *"The NANDA paper argues DNS can't handle a future with billions of fast-moving AI agents — it needs richer metadata, faster updates, real cryptographic trust, and a privacy path. I built a working prototype: a lean index that hands out signed `AgentAddr` pointers, agents publish signed `AgentFacts` documents to separate hosts, and a client walks the chain and verifies every signature before it ever talks to the agent. There's a CLI and a web UI. The headline demo is a tamper button — I mutate the signed metadata in flight and you watch the client refuse to use the rerouted endpoint."*

That's the whole thing. Everything else is detail under that sentence.

---

## Three rehearsable demos (pick based on time)

### A. 90-second wow demo

For when you want to land the impact fast.

1. **`docker compose up -d` is already running.** Skip setup.
2. **Open `http://localhost:8000/ui/`** — say *"this is the index explorer."*
3. **Point at the 3 architecture cards** — *"three tiers from the paper. Stable index, rich metadata, runtime."*
4. **Point at the 2 agents** — *"two registration styles. One agent owns its own facts host, the other uses a third-party — that's the 'quilt' model from the paper."*
5. **Click "Resolve" on the echo agent.** Watch the 5-step cascade animate in. Say:
   - *"Each step is a real HTTP request and a real Ed25519 verify, in the browser."*
   - *"Index pubkey — AgentAddr — verify with index key — fetch the facts — verify with the agent's own key, which was inside the AgentAddr we just verified. That's the chain of custody."*
6. **Scroll to the tamper section. Click "Run attack."** Say:
   - *"Pretend a man-in-the-middle swaps the endpoint URL inside the signed facts."*
   - The page shows: original VALID, tampered INVALID, big red stamp.
   - *"Same Ed25519 verify, runs in your browser. The attacker can mutate any field but they can't forge a signature without the agent's private key."*

That's the demo. Stop talking. Wait for questions.

### B. 5-minute technical demo

Same as above, plus these beats:

- **After step 5**, scroll the JSON cards into view and *show the signature fields are different in AgentAddr vs AgentFacts*. Say: *"Two independent keys. The index signs the pointer record; the agent signs its own metadata. Compromising one doesn't compromise the other."*
- **Then call an agent.** Pick the translate agent, type something, click. *"Resolve runs again first — same five verifications — then we POST to the endpoint we just verified."*
- **Then switch to the CLI in a terminal.** Run:
  ```
  python -m nanda.cli resolve urn:agent:demo:echo
  python -m nanda.cli demo-tamper urn:agent:demo:echo
  ```
  Say: *"Same verifier, same primitive. The CLI and the browser both use Ed25519 over canonical JSON — the browser proves the verification isn't just the server saying 'trust me'."*

### C. 15-minute deep dive (only if asked)

Branch into:
- Open `nanda/crypto.py` — *"30 lines, three functions: keypair, sign, verify. Canonicalize sorts keys and strips whitespace so verification is deterministic across implementations."*
- Open `services/index_service/main.py` — *"FastAPI, SQLite. The signed AgentAddr is built on every resolve so TTL stays fresh; the underlying record never changes."*
- Open `services/facts_host/main.py` — *"Dumb store. Doesn't validate signatures on write. That's the client's job — the paper is explicit that hosts shouldn't be trust anchors."*
- Open `PLAN.md` §9 — *"Here's what I deliberately didn't build, and why."*

---

## Architecture in one diagram + 60 seconds of narration

```
                           ┌────────────────────┐
                  fetches  │                    │
              ┌────────────│   Browser / CLI    │────────────┐
              │            │      (client)      │            │
              │            └────────────────────┘            │
              │                      │                       │
              │ ① GET /              │ ② GET /resolve/{name} │
              ▼                      ▼                       ▼
      ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
      │  Index pubkey │      │ Lean Index    │      │ Agent Endpoint│
      │   (cached)    │      │ ───────────── │      │  POST /echo   │
      └───────┬───────┘      │ SQLite ·  Ed25519   │  POST /xlate  │
              │              │ signs AgentAddr     └───────────────┘
              │              └───────┬───────┘                ▲
              │  ③ verify Addr with  │                        │
              │     index pubkey     │  AgentAddr             │
              └──────────────────────┤  (signed)              │
                                     │                        │
                                     │  ④ GET facts_url       │ ⑥ POST after verify
                                     ▼                        │
                              ┌─────────────────┐             │
                              │ Facts Host      │             │
                              │  primary (8001) │             │
                              │  private (8002) │             │
                              │ stores signed   │             │
                              │  AgentFacts     │             │
                              └────────┬────────┘             │
                                       │  AgentFacts (signed) │
                                       ▼                      │
                          ⑤ verify with agent's pubkey ───────┘
                             (taken from the AgentAddr in ②)
```

**Narration:** *"The index is tiny — it only knows where to find the metadata, not what's in it. The metadata lives on a separate host so it can change minute-to-minute without rewriting the index. Both layers are signed independently by different keys. The client walks both and only talks to the endpoint after both verify."*

---

## Why each technical decision (the inevitable "why X" questions)

### Why Python + FastAPI?
- Fast to build, every service is < 100 LOC.
- FastAPI auto-generates `/docs` — a free interactive UI to show backend APIs.
- You're not building for scale here; you're building for *clarity*.

### Why SQLite, not Postgres?
- Zero infra. No DB server to run. `docker compose up` brings the whole world up.
- The MVP table has eight columns and ~5 rows. Postgres would be a tell that you over-engineered.
- *"If we needed to scale to thousands of registrations per second, Postgres or a KV store would be the swap. The schema is small enough that the migration is trivial."*

### Why Ed25519 + JCS, not full W3C Verifiable Credentials?
- The brief explicitly allows *"signed JSON, W3C Verifiable Credentials, or another approach of your choice."*
- W3C VCs use the same Ed25519 primitive — they wrap it in a JSON-LD `proof` block. For an MVP, the envelope is 80% paperwork and 20% security; the security comes from the primitive.
- **JCS** (RFC 8785, JSON Canonicalization Scheme) gives byte-stable input to the signer regardless of key order or whitespace. Same idea that VCs require.
- *"If a reviewer wanted real VCs, the upgrade is wrapping the existing signature in a `proof` object — schema doesn't change, verification logic doesn't change."*

### Why two facts hosts (primary + private)?
- The paper explicitly distinguishes `PrimaryFactsURL` (agent-owned) and `PrivateFactsURL` (third-party, privacy-preserving).
- Running two demonstrates the "quilt" model concretely — one process template, two roles.
- *"In production, the private host could be IPFS or a CDN. For the MVP it's a second HTTP service so the demo runs without external dependencies."*

### Why CLI **and** a web UI?
- **CLI is the proof of correctness** — terse output, easy to script, easy for a security reviewer to read.
- **Web UI is the proof of comprehension** — turns the abstract chain into something visceral. The tamper demo lands harder visually.
- Both use the same backend; the web UI duplicates the verifier client-side (TweetNaCl) so the green ✓ isn't a backend asserting validity.

### Why no real cloud deployment?
- *"The brief allows local docker-compose. Adding a cloud deploy would mean either spending money or burning a half-day on free-tier auth/domain plumbing — neither of which improves what the reviewer evaluates."*
- The whole stack costs $0 to run.

### Why animated cascade instead of just printing results?
- You're being evaluated on **demo presence** as much as code. A 1.5-second-per-step animation lets you narrate each verification *while it happens*. Static logs don't.
- The tamper demo's red stamp drops with a spring animation — it's a visual punctuation mark you can pause on.

### Why no auth on `/register`?
- Honest scope choice — anyone can register an agent in this demo. Called out in the README.
- *"For production, this would be an OIDC-protected admin endpoint or a slow-mode-rate-limited public endpoint with proof-of-work. Not in scope for proving the resolution architecture."*

### Why TweetNaCl in the browser when I already verify server-side?
- *"Because if the only verifier is the index service, then the index is a trust point of failure. The whole NANDA argument is that clients should verify independently. Running the verify in the browser makes the demo honest — the green checkmark you see is a real check, not the server reporting on itself."*

---

## Component interaction in plain English

### 1. The Index (`services/index_service`)
- Owns a long-lived Ed25519 keypair (`data/index_keypair.json`).
- Stores per-agent rows in SQLite: name, public key, facts URLs, TTL.
- On every `GET /resolve/{name}` it **builds a fresh AgentAddr and signs it.** This means the TTL window is anchored to the time of resolve, not registration — exactly what the paper describes.

### 2. The Facts Host (`services/facts_host`)
- Two instances in compose: one acting as primary (8001), one as private (8002). Same code, different env var.
- Stores AgentFacts JSON blobs on disk by `agent_id`.
- Pure dumb storage. Doesn't validate the signature on `PUT`. *"The host doesn't get to decide what's trustworthy — only the client does."*

### 3. The Agents (`services/agents`)
- The actual endpoints — one echoes, one mock-translates.
- Don't sign or verify anything. They're vanilla services. The signing happens at registration time, in the bootstrap script.

### 4. The Bootstrap (`scripts/bootstrap.py`)
- Runs once after the stack is up.
- For each agent: generates an Ed25519 keypair, registers it with the index, builds the AgentFacts JSON, signs it with the agent's private key, PUTs it to the right host.
- Idempotent — re-running it overwrites cleanly.

### 5. The CLI (`nanda/cli.py`)
- `list` → calls `GET /agents` on the index.
- `resolve` → walks the chain, verifies both signatures, prints the result.
- `call` → resolves, then POSTs a message to the endpoint.
- `demo-tamper` → fetches a real signed facts doc, mutates a field, re-runs the verifier, shows the rejection.

### 6. The Web UI (`frontend/`)
- Single HTML page + one JS file + one CSS file. No build step, no node_modules.
- TweetNaCl loaded from CDN does the actual Ed25519 verify in-browser.
- Same UX surface as the CLI but visualized — the cascade animates, the tamper demo has a stamp animation.
- Served by the index service at `/ui/` so there's no extra process to manage.

---

## Likely interview questions + prepared answers

### "Walk me through what happens when a client resolves an agent."
> *"Client hits `/` on the index to get the index's public key. Then `/resolve/{name}` to get a signed AgentAddr — that's a small JSON record with the agent's public key and pointers to its facts host. Client verifies the AgentAddr signature using the index pubkey. Then fetches the facts URL listed in the AgentAddr, gets back an AgentFacts JSON document, and verifies its signature using the agent's public key — which it learned about in the previous step. Only after both verifications does it use the endpoint listed in the facts."*

### "What stops me from registering a fake agent?"
> *"In this MVP, nothing — `/register` is open. That's an honest scope cut. The paper's answer is W3C Verifiable Credentials issued by trusted authorities. In a real deployment you'd require a credential from a recognized issuer for sensitive namespaces, with revocation via VC-Status lists."*

### "What if the agent's private key leaks?"
> *"Two layers. First, the AgentFacts can be re-issued with a new key — but old signed facts remain valid until the TTL expires, which is why the paper specifies short TTLs (5–15 min for rotating, 30–60 sec for adaptive). Second, the index entry can be re-registered with a new public key, which invalidates all prior facts signed with the old one. The paper goes further with VC-Status revocation lists for sub-second revocation."*

### "Why not just put the public key in DNS?"
> *"DNSSEC kind of does that. The problem is the metadata. DNS records are designed for static IPs; agents need to advertise capabilities, skills, performance metrics, certifications — none of that fits in TXT records cleanly. And DNS propagation is minutes-to-hours, not seconds. The NANDA argument is: keep the lean lookup, but resolve to something richer than an IP — to a signed metadata document hosted wherever the agent wants."*

### "How does the privacy path actually preserve privacy?"
> *"By decoupling who-is-asking from what-is-being-served. If the AgentFacts live on the agent's own server, every lookup tells the agent who's interested. If they live on a neutral third-party host — IPFS in production, our private facts host in the demo — the agent never sees the request. The crypto chain is identical either way."*

### "Why a custom canonical-JSON instead of JOSE / JWS?"
> *"JWS would also work — it's the same primitive plus a base64 envelope. I picked JCS + raw Ed25519 because it's the minimum primitive that proves the architecture works, and it's exactly what the W3C VC Data Integrity spec uses under the hood. The upgrade path to JWS or VC is the same line of code."*

### "What would you build next?"
> *"In order: (1) wrap the existing signatures in a real W3C VC envelope so the wire format matches the paper byte-for-byte. (2) Stand up a real `AdaptiveResolver` service that does geo or load-aware dispatch — the schema field is already there. (3) Plug the bootstrap into a real credential issuer so registration requires a VC. (4) Push the index to free-tier hosting so reviewers can hit a live URL without `docker compose`."*

### "How does this scale?"
> *"The index is the bottleneck — but deliberately a small one. AgentAddr records are ~250 bytes signed, the only DB write is on registration. The paper's claim is 10⁴× fewer writes than DNS because endpoints don't churn the index, they churn the facts host (which can be CDN-cached at the edge). The MVP is single-node SQLite; production would shard by agent_id prefix across a key-value store. None of the architecture changes."*

### "Did you use AI tools?"
> *"Yes — Claude as a pair-programmer for sketching the architecture and drafting service skeletons. Every line I committed I reviewed and ran end-to-end. The crypto layer in particular I rewrote twice to make sure canonicalization actually matches between Python and JavaScript — that's a place where copy-paste-from-LLM would have silently broken signature verification across implementations."*

### "What's the most interesting tradeoff you made?"
> *"Picking JCS+Ed25519 over real W3C VCs. The brief allows either. VCs would have been a bigger talking point but added a full day of JSON-LD context wrangling for the same demo outcome — 'client detects tampering.' I'd rather ship the architecture clearly than ship a half-finished VC envelope."*

### "If you had two more days, what would you change?"
> *"Replace the signature with a proper W3C VC `proof` block, add a real adaptive resolver, and write a test that mutates the AgentFacts in flight (rather than client-side) using an HTTP proxy — that's a more convincing tamper demo."*

---

## A confidence cheat-sheet (read this right before the call)

- **You built it.** It runs. Every signature check is real. You can drop into the source for any layer and explain it.
- **The MVP is honestly scoped.** PLAN.md §9 lists every cut. That's a strength, not a weakness — it shows you can prioritize.
- **You have two surfaces** — CLI and web UI. If one breaks live, you have the other.
- **The tamper demo is the moment.** Hold for it. Let the red stamp land. Then narrate the implication.
- **When you don't know, say "I don't know — here's how I'd find out."** Better than guessing on a spec question.

---

## Live-demo failure modes & recovery

| If… | Do this |
|---|---|
| `docker compose up` fails | Fall back to running each service via `uvicorn` directly. The `docker-compose.yml` has the exact commands. |
| Port 8000 is in use | Run the stack on alt ports and open `/ui/?index=http://localhost:18000&facts1=…` — the frontend honors URL params. |
| Browser can't reach a service | The status pills at the top right turn red. Note which one and refresh — usually it's a slow container startup. |
| Bootstrap script hangs | Check `docker compose logs index` — almost always SQLite file-permission on the mounted volume. `rm -rf data && docker compose up` resets. |
| You forget the demo flow | Open this file (`DEMO_GUIDE.md`) in another tab. The 90-second script is the first section. |

---

## What's in the repo

| File / dir | Why it matters in the interview |
|---|---|
| `PLAN.md` | Shows you planned before you built. Has explicit non-goals. |
| `README.md` | First impression for the reviewer; quickstart that works. |
| `DEMO_GUIDE.md` | (This file.) Your script. |
| `nanda/crypto.py` | 30 lines. The whole trust model lives here. |
| `nanda/cli.py` | Where the chain is most readable end-to-end. |
| `services/*/main.py` | One file per service. Open them on the call. |
| `frontend/app.js` | Same chain as the CLI, in the browser. Look at `runResolutionCascade`. |
| `scripts/bootstrap.py` | Shows how an agent onboards in real life. |
| `tests/test_crypto.py` | 4 tests, all passing. *"I sign-and-verify, I tamper-detect, I reject wrong keys, I canonicalize stably."* |

You're ready. Go take the call.
