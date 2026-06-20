# Interview Walkthrough — NANDA Index Explorer

A speakable script for the live demo portion of the technical interview. Walks the
web UI (`http://localhost:8000/ui/index.html`) top-to-bottom. **Bold** = technical
phrases to land. *If they probe* = the likely follow-up and a crisp answer.

> Goal: show working software, narrate the trust chain, and volunteer the trade-offs
> before you're asked.

---

## Pre-flight (have this running before the call)

```bash
docker compose up --build -d          # all 6 services + web UI
pip install -r requirements.txt       # for the CLI / bootstrap
python scripts/bootstrap.py           # register the 3 demo agents
```

- Web UI: **http://localhost:8000/ui/**
- Design & flow page: **http://localhost:8000/ui/design.html**
- Have a terminal open too, in case they want the CLI (`python -m nanda.cli ...`).

One-line readiness check: all six status dots at the top of the UI should be green.

---

## 0. Opening framing (before clicking anything)

> "This is a working prototype of the NANDA paper's core idea: replace DNS-style
> lookup for AI agents with a **signed metadata chain**. The whole design follows
> from one move — **split identity from metadata** — so the index stays tiny and
> rarely-written, while the rich, fast-changing data lives in separate signed
> documents. Everything verified on this page is checked **client-side in the
> browser with Ed25519 (TweetNaCl)** — no server is trusted to vouch for itself."

---

## 1. Service status (top-right pills)

> "Six services: the lean **index** on 8000, two **facts hosts** — 8001 agent-owned,
> 8002 third-party — two **agents** on 8010/8011, and the **adaptive resolver** on
> 8020. All green means the stack is healthy."

---

## 2. Architecture — three tiers

> "Tier 1, the **Lean Index**, returns a tiny signed pointer called an **AgentAddr**.
> Tier 2, **AgentFacts**, is the rich signed credential. Tier 3 is the actual
> **agent endpoint**. The index never holds capabilities or endpoints — that's what
> keeps it lean, and it's the paper's headline claim: roughly **10⁴× fewer index
> writes than DNS**."

---

## 3. Registered agents — the "quilt"

> "Three agents, three registration styles from the paper: **echo** hosts its facts
> on its own host; **translate** delegates to a neutral third-party host — that's the
> **privacy path**; **multiregion** adds an **adaptive resolver**. Same index,
> different hosting and routing — that's the 'quilt'."

---

## 4. Resolution cascade — *the core; spend the most time here*

Click **Resolve** on echo, then narrate the 5 steps:

> "Step 1 fetches the **index's public key** — the single trust anchor. Step 2
> resolves the name to a signed **AgentAddr**. Step 3 **verifies that signature**
> against the index key — you can see the real `nacl.sign.detached.verify` call over
> **JCS-canonical JSON (RFC 8785)**. Step 4 follows the pointer and fetches the
> **AgentFacts**, which is a **W3C Verifiable Credential v2 with a DataIntegrityProof,
> cryptosuite eddsa-jcs-2022**. Step 5 verifies *that* signature — but with the
> agent's key, which came **from inside the AgentAddr**. That's the chain of custody:
> trust flows from one anchor."

**If they probe "why two signature types?"**
> "AgentAddr is just a pointer the index asserts — a plain detached signature is
> enough. AgentFacts is a *claim about an agent*, so it gets the full VC envelope,
> interoperable with any VC verifier. Same Ed25519 primitive, two envelopes."

**If they probe "why JCS / canonical JSON?"**
> "JSON can be serialized many ways — key order, whitespace. If you signed raw bytes,
> a verifier that re-serialized differently would compute a different hash and the
> signature would falsely fail. JCS (RFC 8785) forces one canonical byte sequence so
> signer and verifier always agree."

**If they probe "why not full W3C VCs / a VC library?"**
> "The brief allowed signed JSON or VCs. I ship the real VC wire format — the
> `eddsa-jcs-2022` cryptosuite *is* Ed25519 over JCS — but without dragging in a
> 300-line JSON-LD stack. It's interoperable with VC-aware verifiers and ~30 lines."

---

## 5. Call an agent — + adaptive routing

Select **multiregion**, tick **Use Adaptive Resolver**, region **eu-west**, click
**Resolve & Call**:

> "It re-runs the full verification first — we never call an endpoint we haven't
> verified. Then steps 6–7 are the adaptive path: it asks the **resolver**, which
> returns a **signed, 60-second TTL routing token**, and the client **verifies the
> resolver's signature** before using the endpoint. With eu-west, geo policy
> dispatches to the EU endpoint. Switch to us-east and it routes elsewhere — same
> name, different backend, proven with a signature."

**If they probe "what stops a forged endpoint?"**
> "The routing token is signed by the resolver's own key, which is carried in the
> token and verified client-side. And it expires in 60 seconds, so even an
> intercepted token has a tiny damage window."

---

## 6. Tamper detection — the security punchline

Select echo, click **Run attack**:

> "This simulates a man-in-the-middle swapping the endpoint URL inside the signed VC.
> The original verifies; the mutated one **fails** — because the attacker **can't
> forge a new DataIntegrityProof without the agent's private key**. The client
> re-canonicalizes, runs Ed25519 verify, sees the byte mismatch, and **refuses to
> call** the evil endpoint. That's the brief's 'detect tampering' requirement, proven
> live."

---

## 7. Close — Design & Flow page + limitations

Open **design.html** briefly:

> "The Design & Flow page has the full sequence diagrams, the trust hierarchy, the
> **design rationale**, and an honest **limitations** table. The biggest deferred
> piece is **revocation** — the paper centers sub-second VC-Status revocation; I ship
> TTL expiry only, and I can walk through how I'd add a VC-Status list."

Volunteering the revocation gap shows you read the paper critically and pre-empts the
most likely deep-dive.

---

## Quick reference — phrases to land

- **Split identity from metadata** → lean index, ~10⁴× fewer writes than DNS
- **AgentAddr** = signed pointer (detached Ed25519 sig, signed by index)
- **AgentFacts** = **W3C VC v2**, **DataIntegrityProof**, **eddsa-jcs-2022** (signed by agent)
- **Ed25519 over JCS-canonical JSON (RFC 8785)** — same primitive everywhere
- **One trust anchor** (index pubkey) → chain of custody to the agent pubkey
- **Client-side verification** (TweetNaCl in browser, PyNaCl in CLI)
- **Adaptive resolver** = signed, 60s-TTL routing token (geo / capability / round-robin)
- **Three keypairs**: index, agent, resolver — blast radius isolated per key

## Known limitations to own (don't hide these)

| Gap | Status | One-line answer |
|---|---|---|
| Revocation / VC-Status | TTL expiry only | Add a VC-Status list credential + status check in verify |
| DID resolution | URN only | Add `did:web` / `did:key` |
| Privacy transport | 2nd HTTP host | Real anonymity needs IPFS / Tor |
| Enterprise quilt | 2 of 6 Table-1 styles | Add enterprise-routed + Web3/DID styles |
| Index federation | single index | Cross-index verifiable links |
| `/register` auth | open | Needs auth + rate limiting in prod |
| Storage | SQLite | Sharded KV store for 10k resolves/sec/shard |
