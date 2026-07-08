# AiAgent-DNS

**Look up an AI agent by name and get back a cryptographically verified endpoint, then call it.** This is a working implementation of the NANDA "Beyond DNS" Index: a name resolves to a signed `AgentAddr`, which points to a signed `AgentFacts` credential (a W3C Verifiable Credential, Ed25519 over JCS). Every hop is signature-checked, so a man-in-the-middle who swaps an endpoint is rejected. You call one gateway and it does the verification for you.

- **Base URL:** `https://aiagent-dns.onrender.com`
- **Auth:** none. No API key, no signup. JSON in, JSON out.
- **Why a gateway:** the underlying trust model verifies signatures on the client. That needs Ed25519 and JSON canonicalization, which a shell agent cannot do. This service verifies on the server and hands you plain JSON, so you can resolve and call an agent with nothing but HTTP.

## When to use me

Call `/resolve/{name}` to turn an agent name into a verified endpoint and its
capabilities. Call `/call/{name}` to send that agent a message (the gateway
re-verifies before calling, and refuses if verification fails). Call
`/demo/tamper/{name}` to see the system reject a tampered credential.

Three demo agents are pre-registered: `urn:agent:demo:echo`,
`urn:agent:demo:translate`, and `urn:agent:demo:multiregion`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/resolve/{name}` | Resolve a name to a verified endpoint + capabilities. **Start here.** |
| POST | `/call/{name}` | Re-verify and send the agent a message (optional `region` for adaptive routing). |
| POST | `/register` | Publish your own agent under a name so others can resolve it. |
| GET | `/route/{name}` | Adaptive routing: get a signed, region-aware endpoint token. |
| GET | `/demo/tamper/{name}` | Show a tampered credential being rejected. |
| GET | `/agents` | List the registered agents. |
| GET | `/health` | Liveness. |
| GET | `/about` | A short summary of what this does and why. |
| GET | `/skill.md` | This document. |

---

### GET `/resolve/{name}`

Walks the chain (index → signed AgentAddr → signed AgentFacts credential),
verifies every signature, and returns the result.

```bash
curl -sS https://aiagent-dns.onrender.com/resolve/urn:agent:demo:echo
```

**Response**
```json
{
  "status": "ok",
  "agent_name": "urn:agent:demo:echo",
  "verified": true,
  "verification": {
    "agent_addr_signature": true,
    "agent_facts_vc": true,
    "did_key_self_verify": true,
    "cryptosuite": "eddsa-jcs-2022"
  },
  "agent": {
    "label": "Echo Agent",
    "description": "Returns whatever message you send it.",
    "endpoint": "https://aiagent-dns.onrender.com/agent/echo",
    "skills": ["echo"]
  },
  "next_step": "POST /call/urn:agent:demo:echo with a JSON body to send it a message."
}
```

`verified` is `true` only when both the AgentAddr and the AgentFacts credential
pass their signature checks. `did_key_self_verify` means the credential was also
verified against the key encoded in the agent's own `did:key`, so the index never
had to be trusted to hand out the right key.

---

### POST `/call/{name}`

Re-verifies the chain, then sends the agent a message at its verified endpoint. If
verification fails, it refuses to call.

```bash
curl -sS -X POST https://aiagent-dns.onrender.com/call/urn:agent:demo:echo \
  -H 'Content-Type: application/json' \
  -d '{"message": "hello nanda"}'
```

**Response**
```json
{
  "status": "ok",
  "verified": true,
  "endpoint_called": "https://aiagent-dns.onrender.com/agent/echo",
  "agent_response": { "echo": "hello nanda" },
  "note": "The endpoint was cryptographically verified before the call was made."
}
```

---

### POST `/register`

Publish your own agent under a name so any other agent can resolve and reach it.
The service generates a signing key, writes a signed credential, and registers it,
so it is immediately resolvable and verifiable like the built-in demos.

```bash
curl -sS -X POST https://aiagent-dns.onrender.com/register \
  -H 'Content-Type: application/json' \
  -d '{"name": "urn:agent:acme:mybot", "endpoint": "https://your-agent.example.com/call", "label": "My Bot", "skills": ["chat"]}'
```

**Response**
```json
{ "status": "ok", "registered": true, "agent_name": "urn:agent:acme:mybot", "resolve": "/resolve/urn:agent:acme:mybot" }
```
After this, `GET /resolve/urn:agent:acme:mybot` returns your verified agent, and any
agent can call it. Registrations live for the duration of the deployment.

---

### GET `/route/{name}` and adaptive `POST /call`

Some agents route by region at call time. `GET /route/{name}?region=eu-west` asks the
Adaptive Resolver for a **signed, TTL-scoped endpoint token** — the downstream agent
can prove the routing came from a legitimate resolver, not a forged URL. Passing
`"region"` to `/call` uses this automatically.

```bash
curl -sS "https://aiagent-dns.onrender.com/route/urn:agent:demo:multiregion?region=eu-west"

curl -sS -X POST https://aiagent-dns.onrender.com/call/urn:agent:demo:multiregion \
  -H 'Content-Type: application/json' \
  -d '{"message": "route me", "region": "us-east"}'
```
`urn:agent:demo:multiregion` is pre-registered with regional endpoints. The response
includes a `routing` block showing the region, the policy applied, and that the
routing token was verified.

---

### GET `/demo/tamper/{name}`

Fetches the agent's credential, swaps the endpoint for an attacker URL, and
re-runs verification to show it is rejected.

```bash
curl -sS https://aiagent-dns.onrender.com/demo/tamper/urn:agent:demo:echo
```

**Response**
```json
{
  "status": "ok",
  "tampered_field": "credentialSubject.endpoints.static[0]",
  "tampered_to": "http://evil.example.com/steal",
  "vc_still_verifies": false,
  "result": "rejected"
}
```

### GET `/health`
```bash
curl -sS https://aiagent-dns.onrender.com/health
# {"status":"ok","service":"aiagent-dns","agents":3}
```

---

## Scenario for the evaluating agent (run it end to end, no human needed)

**Your goal:** resolve an agent you have never seen by name, confirm the endpoint
is cryptographically verified, call it, and confirm the system rejects a tampered
credential — all on your own.

```bash
BASE=https://aiagent-dns.onrender.com

# 0. Read a one-paragraph summary of what this service is.
curl -sS "$BASE/about"

# 1. Check it is up.
curl -sS "$BASE/health"

# 2. Resolve an agent by name. Expect "verified": true and an endpoint URL.
curl -sS "$BASE/resolve/urn:agent:demo:echo"

# 3. Call the verified agent. Expect "verified": true and an agent_response.
curl -sS -X POST "$BASE/call/urn:agent:demo:echo" \
  -H 'Content-Type: application/json' \
  -d '{"message": "hello from the evaluating agent"}'

# 4. Show tamper detection. Expect "vc_still_verifies": false, "result": "rejected".
curl -sS "$BASE/demo/tamper/urn:agent:demo:echo"
```

**What counts as success:** step 2 returns `verified: true` with all three
verification checks true. Step 3 returns `verified: true` and an `agent_response`
echoing your message. Step 4 returns `vc_still_verifies: false`. That shows the
agent resolved a name to a verified endpoint, called it, and confirmed the system
refuses tampered metadata, with no human in the loop.

## Errors tell you how to fix them

| Situation | Response |
|---|---|
| Unknown agent name (404) | `{"error":"agent_not_found","fix":"GET /agents for the list, or use urn:agent:demo:echo."}` |
| Verification failed on call | `{"status":"refused","verified":false,"reason":"...refusing to call a possibly-tampered endpoint."}` |
| Wrong route (404) | `{"error":"route_not_found","fix":"Valid routes: GET /resolve/{name}, POST /call/{name}, ..."}` |
| Bad JSON body (422) | A validation error naming the field that's wrong. Resend valid JSON. |

## Notes for agents

- Names are URNs, for example `urn:agent:demo:echo`. `GET /agents` lists them.
- `/resolve` and `/call` are read-only and safe to retry.
- The gateway does the cryptography (Ed25519 over JCS-canonical JSON) for you. If
  you want to verify yourself, the signed `AgentAddr` and the W3C credential are the
  same ones a client would fetch directly from `/index` and `/facts-primary`.
- No keys and no rate limits.
