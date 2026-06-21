# Full Interview Walkthrough Script

A complete, speakable narration of the whole project — backend, frontend, crypto,
flow, limitations, and scaling. Practice it out loud. **Bold** = phrases to land.
*If they probe* = the likely follow-up and a crisp answer.

Order: opener → architecture → backend/uvicorn → crypto → end-to-end flow →
frontend → CLI → did:key → limitations → scaling/production → vs DNS → close.

---

## 0. The 60-second opener

> "The challenge was to prototype the NANDA paper, *Beyond DNS*. The core idea:
> DNS maps a name to a static IP and proves only domain *ownership* — that breaks
> for AI agents that move every few seconds and need verifiable *capabilities* and
> sub-second revocation. So NANDA splits a lookup into a **tiny signed pointer**
> (the AgentAddr) plus **rich signed metadata** (AgentFacts), so the index stays
> lean while the metadata stays fresh. I built the full flow end-to-end:
> **client → index → AgentAddr → AgentFacts → endpoint**, with every step verified
> cryptographically, and a few Level-2 extensions on top."

---

## 1. Architecture at a glance

> "It's a **distributed system, not a monolith** — six independent services, each a
> small FastAPI app on its own port, plus a static web UI and a CLI client. Three
> tiers from the paper:
> - **Lean Index** (:8000) — signs the AgentAddr pointer record.
> - **AgentFacts hosts** (:8001 primary, :8002 private) — store the signed metadata.
> - **Dynamic resolution** — the **Adaptive Resolver** (:8020) picks a live endpoint.
> - Plus two sample **agents** (:8010 echo, :8011 translate) the client actually calls.
>
> The whole thing comes up with one `docker compose up`, and the browser or CLI acts
> as the **client** that stitches the services together and verifies their signed
> responses."

---

## 2. The backend — FastAPI + uvicorn

> "Every service is **FastAPI**. Coming from Django, the shift is that the route,
> method, input validation, and output shape all live **on the function** via a
> decorator and type hints — no `urls.py`, no separate serializer. FastAPI doesn't
> run itself; an ASGI server called **uvicorn** serves it. So in `docker-compose.yml`
> each service has its own line like `uvicorn services.index_service.main:app
> --port 8000` — uvicorn **imports the `app` object** and serves it. That's why the
> services have **no `if __name__ == '__main__'`** — only the CLI does, because I run
> the CLI directly."

**Storage:** *"The index is **SQLite** — a real SQL database, just embedded. The facts
hosts are deliberately dumb key→document stores (flat files), and keys are JSON files.
Each storage type is chosen deliberately — a DB where I query, files where a DB is overkill."*

*If they probe "why six services not one app?":* "Because the paper's architecture is
distributed — the index, facts hosts, agents, and resolver are separate *actors*
(different owners, trust domains). A monolith would hide exactly what the paper is about."

---

## 3. The crypto core — the heart (`nanda/crypto.py`)

> "Everything rests on **Ed25519 signatures over RFC 8785 canonical JSON (JCS)**.
> Canonicalization matters because JSON can be serialized many ways — JCS forces one
> byte sequence (sorted keys, no whitespace) so a signature made on the server
> verifies in the browser with no re-signing. I use **PyNaCl** (libsodium) on the
> server and **TweetNaCl** in the browser — same Ed25519 primitive, so it's
> cross-language interoperable.
>
> Two signing shapes: a plain **detached signature** for the AgentAddr (a record the
> index asserts), and a **W3C Verifiable Credential v2 with a DataIntegrityProof,
> cryptosuite `eddsa-jcs-2022`** for AgentFacts (a *claim about an agent*). The
> cryptosuite name is literal — `eddsa` = Ed25519, `jcs` = the canonicalization."

*If they probe "why not full W3C VCs with a library?":* "I ship the real VC wire
format but without a 300-line JSON-LD dependency — it's interoperable with any
VC-aware verifier in ~30 lines. The brief allowed signed JSON or VCs."

*Signing ≠ encryption:* "These signatures give **integrity + authenticity**, not
confidentiality. The index is public-read like DNS — anyone can fetch an AgentAddr;
the signature lets the reader prove it wasn't tampered with and came from the real
index. That's *why* a man-in-the-middle who edits the metadata gets caught."

---

## 4. The end-to-end flow — three signatures, three keys

Walk the **adaptive call on the multiregion agent**:

> "There are **three keypairs**: the index signs the AgentAddr, each agent signs its
> own AgentFacts, the resolver signs routing tokens. The client only trusts **one
> thing up front — the index's public key** — and trust chains from there.
>
> 1. **Fetch the index public key** — the trust anchor.
> 2. **Resolve the name → signed AgentAddr.** Verify it with the index key.
> 3. The AgentAddr **carries the agent's public key** — that's the bridge.
> 4. **Fetch the AgentFacts VC** from the facts host (a dumb store — it doesn't verify).
> 5. **Verify the VC** with the agent key *from step 2* — that's the **chain of custody**.
> 6. **Dispatch via the Adaptive Resolver** — it returns a **signed, 60-second routing
>    token** naming the chosen endpoint.
> 7. **Verify the token** with the resolver's key.
> 8. **Only now** — after three verified signatures — call the endpoint.
>
> All three checks run **client-side in TweetNaCl** — the green checks are real
> cryptography the reviewer can audit, not a server saying 'trust me.'"

---

## 5. The frontend

> "The UI is **build-step-free**: plain HTML, **vanilla JavaScript**, **Tailwind via
> CDN**, **TweetNaCl** for in-browser Ed25519, and **Mermaid** for diagrams. No
> framework, no bundler, no `node_modules` — served as static files by the index at
> `/ui/`. I chose vanilla on purpose: the point is *transparency* — a reviewer can
> read `app.js` and see exactly what's fetched and verified. The verification runs
> in the browser, so the trust checks are genuine, not server-confirmed.
>
> There are five pages: the **live demo**, **how the code works**, **production at
> scale**, **compared to DNS**, and a **design & flow** diagram page."

Demo to click live: **Resolve** (verify-only, never calls the agent) vs **Resolve &
Call** (verify + invoke); the **adaptive** path with the round-robin region banner;
and **Tamper detection** — mutate the signed VC and the client rejects it.

---

## 6. The CLI (`nanda/cli.py`)

> "The CLI is the technical surface — same chain as the UI, but it prints every
> signature check. It's built with **Typer**: each command is an `@app.command()`
> function, parameters become arguments and `--flags` from the type hints — same
> self-documenting style as FastAPI. Five commands: `list`, `resolve`, `call`,
> `verify-did`, `demo-tamper`. It's a **client** — it needs the stack running and
> talks to the services over HTTP."

---

## 7. The did:key extension (the paper-faithful one)

> "By default I embed the agent's public key in the AgentAddr. To be more
> paper-faithful I added **did:key resolution**: the agent's VC identifies its issuer
> as a `did:key`, which **encodes the Ed25519 key inside the identifier** (the `z6Mk`
> prefix is the Ed25519 multicodec). The `verify-did` command recovers the key
> straight from the credential's `verificationMethod` — so the index's key copy
> becomes a convenience, not a trust requirement. `did:key` needs zero infrastructure
> because the key lives in the identifier."

---

## 8. Limitations — own them before they ask

> "I implemented Level 1 fully and chose a few Level-2 extensions that demonstrate the
> trust model deeply — the VC envelope, the adaptive resolver, the dual-host privacy
> path, and did:key. I **deliberately deferred** several things, and that's a judgment
> call, not an oversight — four solid features beat ten shallow ones."

The honest list (also on the design + code pages):
- **Revocation** — TTL expiry only; the paper centers sub-second VC-Status revocation. *Biggest gap; I can walk through how I'd add it.*
- **DID** — `did:key` done; `did:web` and DID-based names not.
- **Privacy path** — a 2nd HTTP host, not real IPFS/Tor anonymity.
- **Plaintext keys** in `data/` — production needs a KMS/HSM. *(Volunteer this — it's a security instinct.)*
- **`/register`** is open — needs auth + rate-limiting.
- **SQLite / single index** — no sharding, no federation yet.
- IPFS/Tor, ZKPs, trillion-scale, enterprise registry types — out of scope.

> "Each is in the limitations table with an upgrade path."

---

## 9. Scaling & production (system design)

> "The MVP proves the concepts; running it at the paper's scale — trillions of agents,
> &lt;1 s global resolution, sub-second revocation — is a different problem. The key
> moves:
> - **Lean index → sharded, replicated KV store** (hash by agent_id), 10k updates/s/shard.
> - **Edge caching + CDN + anycast** for &lt;1 s; because objects are signed, they're
>   safe to cache on untrusted edges — that's the architectural win: *crypto enables
>   availability, not just security.*
> - **CAP**: resolution is **AP** (signed + TTL-bounded makes eventual consistency
>   safe); revocation leans CP; reconciled with short TTLs + a fast revocation list.
> - **Keys in KMS/HSM**, real VC-Status revocation, DID resolution, auth on writes.
> - **Polyglot persistence**: KV for the index, object/IPFS for facts, append-only log
>   for audit.
> - **Reverse proxy** (Envoy/NGINX) for the adaptive resolver + gateway; **forward
>   proxy** (Tor/relay) for the privacy path.
> - **SLOs/error budgets**, OpenTelemetry tracing, multi-region failover, backups with
>   RPO/RTO, graceful degradation from signed caches.
>
> Throughput and latency are optimised separately — latency via caching/locality,
> throughput via sharding — and caching is the highest-leverage lever because it cuts
> both."

*(All of this is on the **Production at scale** page — use it as the whiteboard outline.)*

---

## 10. vs DNS (the paper's thesis)

> "NANDA isn't replacing DNS — it **keeps** what made DNS reliable for 40 years
> (caching, TTLs, anycast, hierarchy, redundancy, lean records, eventual consistency,
> signed records) and **adds** what DNS structurally can't give agents: verifiable
> capabilities, sub-second revocation, privacy-preserving lookups, and dynamic
> routing. And the leanness that makes DNS cheap is what lets NANDA stay affordable —
> the costly parts (rich metadata, verification) are pushed to the edges and paid by
> whoever benefits. It's **DNS's operating model, re-pointed from static hosts to
> trust-aware AI agents.**"

---

## 11. Likely deep-dives — have these ready

- **"How would you add revocation?"** → a VC-Status list credential + a status
  endpoint the client checks during verify; short-TTL VCs bound the window.
- **"Why JCS / canonical JSON?"** → without it, re-serialization changes the bytes and
  a valid signature falsely fails; JCS removes that ambiguity.
- **"Where's the agent's key in the paper vs your MVP?"** → paper stores a credential
  hash and resolves via DID; I embed the pubkey in the AgentAddr for simplicity, and
  did:key is the faithful path.
- **"What stops a forged endpoint in adaptive routing?"** → the routing token is
  signed by the resolver and expires in 60 s.
- **"AP or CP?"** → AP for resolution (availability), tunable consistency for
  revocation via TTL + revocation list. PACELC: PA/EL — latency-first to hit &lt;1 s.

---

## Closing line

> "So end to end: a lean signed index, rich signed AgentFacts as W3C VCs, an adaptive
> resolver with signed routing tokens, client-side verification in both a CLI and a
> browser, tamper detection, and did:key resolution — all running from one
> `docker compose up`, with an honest limitations list and a clear path to production
> scale. The crypto and the resolution flow are already production-shaped; what
> changes for real scale is the storage, hosting, key management, and federation
> around them."
