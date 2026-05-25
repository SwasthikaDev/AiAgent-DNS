# 🎥 NANDA Pre-Interview Video — Complete Script & Production Guide

> The single file to open while preparing the video for the Project NANDA VP of Engineering submission.
> Read this twice. Practice once. Record three takes. Pick the cleanest. Submit.

---

## Table of contents

1. [The 30-second pitch (memorize)](#the-30-second-pitch-memorize)
2. [Three lines to commit to memory](#three-lines-to-commit-to-memory)
3. [Pre-recording setup](#pre-recording-setup)
4. [Full script — Sections 1 through 9](#full-script--sections-1-through-9)
5. [Time budget at a glance](#time-budget-at-a-glance)
6. [Shot list](#shot-list)
7. [Pauses and emphasis](#pauses-and-emphasis)
8. [Emotional vs technical balance](#emotional-vs-technical-balance)
9. [Q&A primer — likely questions, prepared answers](#qa-primer--likely-questions-prepared-answers)
10. [Things deliberately left out](#things-deliberately-left-out)
11. [Final advice + submission checklist](#final-advice--submission-checklist)

---

## The 30-second pitch (memorize)

> *"I'm [Swasthika], applying for VP of Engineering at Project NANDA. I read the Beyond DNS paper, shipped a working prototype of the lean index, AgentFacts, and the privacy path in two days, and built two surfaces on top — a CLI for technical depth and a web UI where the verification actually runs in the browser. The headline demo is one click: I mutate a signed document in flight and the client refuses to use the rerouted endpoint. There's a public repo, a plan document with explicit non-goals, and a five-minute screen-share that walks the whole chain end to end."*

If you can deliver that in one breath, you can deliver the video.

---

## Four lines to commit to memory

If you forget everything else, remember **these four lines**. Each one signals you understood a specific thing — about the paper, about the system, or about how to lead a team. Hitting all four across the video is more powerful than saying "I studied the paper" once.

1. *"Same Ed25519 primitive that W3C Verifiable Credentials are built on, signed over RFC 8785 canonical JSON."* — proves you read §VII.
2. *"The privacy path from Section VII is a real path, not a config flag."* — proves you implemented it.
3. *"The architecture is designed to contain blast radius."* — proves you think about failure modes, not just happy paths.
4. *"I'd rather defend a small system clearly than a half-finished large one."* — proves you can lead.

---

## Pre-recording setup

### Hardware & space

- **Camera:** eye-level, not below. Webcam at the top of your monitor.
- **Lighting:** one warm light source from the front, slightly above. No window behind you.
- **Background:** clean wall or a soft-blurred room. No empty mugs.
- **Audio:** earbuds with mic if you don't have a USB mic. Test playback first — bad audio kills more videos than bad lighting does.
- **Mode:** Do Not Disturb on phone and laptop. Close Slack, mail, anything that notifies.

### Tabs to pre-open

1. `http://localhost:8000/ui/` — landing page, scrolled to top
2. A terminal with `python -m nanda.cli` ready
3. Code editor open to `nanda/crypto.py`

### Pre-flight checklist (run 5 min before recording)

- [ ] `docker compose up -d` confirms all 5 services healthy
- [ ] `python scripts/bootstrap.py` registered both agents
- [ ] `python -m nanda.cli list` shows two rows
- [ ] In the browser, clicking **Resolve** on the echo agent reaches "Trust chain complete"
- [ ] Clicking **Run attack** in the tamper section shows the red INVALID badge
- [ ] Mic gain set so peaking stays below clipping
- [ ] Phone face-down and silenced

---

## Full script — Sections 1 through 9

> Stage directions in *italics*. Visual cues in **[brackets]**. **Emphasis** in bold.
> Total length target: **~5:00**.

---

### 🎬 Section 1 — Opening hook (0:00 – 0:20) · face to camera

> *Soft smile. Warm but not bouncy. Look directly at the lens, not the screen.*

"Hi — I'm **[Swasthika]**. I'm applying for the **VP of Engineering** role at Project NANDA.

I'm going to spend the next five minutes showing you what I built for the challenge — but more importantly, I want you to understand **why** I built it the way I did.

Because the answer to *that* is the answer to whether we'd work well together."

> *Slight pause. Cut to screen share showing the landing page of the web UI.*

**[VISUAL: web UI landing page — clean, light theme, your name visible in the URL bar]**

---

### 🎬 Section 2 — Who I am, in 40 seconds (0:20 – 1:00) · voiceover with UI in frame

> *Speak conversationally — like you're explaining over coffee.*

"Quick context on me. I've spent the last **[X years]** building **[backend systems / distributed services / what you've actually built]**. My current role is at **[Calyrex]** — and one thing I want to flag early is that **we run our own on-premise infrastructure** there, not just cloud. So when this paper talks about agents being hosted on agent-owned domains, on third-party hosts, or on neutral public infrastructure, those aren't abstractions to me. I've spent real time on the trade-offs — who hosts what, who trusts whom, what fails when a region goes down.

What pulled me into this challenge isn't that I needed *a* job. It's that the NANDA paper points at a problem I've quietly believed for two years — that we are about to ask the existing internet to do something it wasn't designed for. And nobody is treating that as an emergency yet."

> *Emphasize **"nobody is treating that as an emergency."** Brief pause.*

> **Personalization note:** confirm `[Calyrex]` spelling and adjust if needed. The whole point of this beat is to land "I have real infra experience, not just toy-project experience" — swap in whatever framing makes that true for you.

---

### 🎬 Section 3 — The problem, made relatable (1:00 – 1:35) · back to face

> *Lean in slightly. This is the moment to be a teacher, not a candidate.*

"Here's the thing. DNS was designed in 1983. It maps a name like `google.com` to a static IP address. It assumes the thing you're looking up has a fixed home that rarely changes.

Now imagine **billions of AI agents** — booking flights, negotiating contracts, talking to each other. They move every few seconds. They have skills that need to be advertised. They need to be trusted — *is this really the Salesforce agent or someone pretending?* And they need privacy — you shouldn't have to reveal who *you* are just to ask if an agent exists.

DNS can't do any of that. It's a phonebook. We need something closer to a verified directory with a security guard at the door.

That's what the NANDA paper proposes. And that's what I built."

> *Pause. Switch back to screen share.*

**[VISUAL: scroll slowly down the UI showing the three-tier architecture cards]**

---

### 🎬 Section 4 — Why I started building (1:35 – 2:00) · screen share with brief face cut-in

> *Voice slightly warmer, like you're admitting something.*

"When I first read the brief, I almost overscoped. I sketched a full W3C Verifiable Credential implementation, real DID resolution, IPFS for the privacy path, even an adaptive resolver service.

Then I stopped and asked the question I think a VP of Engineering has to ask first: **what's the minimum I can build that proves the architecture works, and what do I have to deliberately not build to ship in two days?**

I wrote that decision down before I wrote any code. It's in the repo as `PLAN.md`. The non-goals section is the part I want a reviewer to read first."

> *Cut briefly to face. Hold for one second. Cut back to screen.*

---

### 🎬 Section 5 — The product, walked through live (2:00 – 3:10) · screen share, narrate the demo

> *This is the headline. Slow down. Let the animations breathe.*

"OK — let me show you what runs.

This is a five-service stack on `localhost`. A lean index, two facts hosts, two demo agents. Everything signed with **Ed25519**."

**[VISUAL: hover over the two agent rows]**

"Two agents are registered. One uses an agent-owned facts host — that's the primary registration style. The other uses a third-party facts host — that's the privacy path from section seven of the paper. The **'quilt' model**, in two records."

> *Click **Resolve** on the echo agent. Stay silent for one beat as the cascade animates.*

**[VISUAL: 5-step cascade animating in]**

"Watch this. Every green check is a real HTTP fetch and a real Ed25519 verification, **in your browser**, using TweetNaCl.

I want to be specific about the crypto: I used the **same Ed25519 primitive that W3C Verifiable Credentials are built on, signed over RFC 8785 canonical JSON**. So the signatures the client verifies here are wire-compatible with where the paper points — wrapping them in a full VC envelope is an additive change, not a rewrite.

And critically, the client isn't asking the server *'is this valid?'* The client is verifying independently. That's important — if the index were the only verifier, the index would be a single point of trust failure."

> *Wait for the green "Trust chain complete" banner.*

**[VISUAL: scroll to tamper section]**

"And the headline demo." *Click **Run attack**.*

> *Wait for the red INVALID badge to land. **One full second of silence.***

"A man-in-the-middle just mutated the endpoint inside the signed facts. The client re-canonicalized the document, re-ran Ed25519 verify, and refused to call `evil.example.com`. The attacker can mutate any field — but they can't forge a new signature without the agent's private key.

That, in one click, is the whole security argument of the paper, demonstrated live."

---

### 🎬 Section 6 — How it works (3:10 – 3:45) · back to face

> *Calmer pace. You're proving you actually understand it.*

"Architecturally — three layers, mapped directly to the paper. A **lean index** that returns signed `AgentAddr` records, the way Section IV describes. **AgentFacts documents**, issued as W3C Verifiable Credentials with a `DataIntegrityProof`, hosted on separate services — primary and private — so the privacy path from Section VII is a *real* path, not a config flag. And the **endpoints**, only called after every signature verifies in sequence.

One more thing on the hosting model. The paper explicitly supports three deployment topologies — agent-owned, third-party, and neutral public infrastructure. This MVP runs all three side by side: the primary host plays the agent-owned role, the private host plays the third-party role, and the Adaptive Resolver plays the role of a neutral runtime authority. In production, an enterprise like ours would pick the mix based on who they trust with what."

---

### 🎬 Section 6.5 — What I shipped, what I cut, why (3:45 – 4:15) · face, calm and confident

> *This is the move. Read it slowly. Don't apologize for any of it. Each cut is reasoned.*

"I want to be straight about what I built versus what the paper specifies — because the gap *is* the engineering decision.

**What I shipped:** the full resolution spine — index, AgentAddr, AgentFacts, dual hosting, signed metadata, TTL caching, in-browser verification, tamper detection. That's the paper's central argument, end to end.

**What I deferred, and why:** the full W3C VC envelope, because the brief explicitly allows the signing approach I used — and the primitive is identical, the wrapping is mechanical. The Adaptive Resolver as a separate service, because the schema field models it but a real implementation would need geo-routing logic that doesn't add to the security story. IPFS for the privacy path, because a second HTTP host demonstrates the *decoupling* property without dragging in distributed storage. And the W3C-issuer trust zones, because there's no point modeling federation when there's no second federation to test against.

Every cut is in `PLAN.md` section nine, with the reasoning. **I'd rather defend a small system clearly than a half-finished large one.**"

---

### 🎬 Section 6.7 — Risk model · what fails if one bad actor enters (4:15 – 4:45) · face, serious

> *Slow down. This is the part where you sound like an engineer who has been on-call, not just one who has built features. Don't be alarmist — be calibrated.*

"One thing I want to talk about that the paper hints at but doesn't dramatize. The honest danger with any agent registry is: **what happens when one malicious agent gets in?** A flat trust model where every registered agent is implicitly trustworthy — a single bad actor can spoof capabilities, impersonate a known provider, poison a supply chain, or quietly reroute traffic to themselves. By accident *or* by intent.

The architecture is designed to contain blast radius. **Per-agent keys** — compromising one agent doesn't compromise the index. **Independent index signatures** — a compromised facts host can't reroute the chain, because the AgentAddr was signed by a different key. **Short TTLs** — even a successful attack has a five-minute window, not forever-in-DNS-cache. And **W3C VC-Status revocation** — which I've put in the 90-day roadmap, not yet shipped — gives sub-second pull-the-plug capability when something is detected.

What's not solved yet, honestly: there's no Sybil prevention on `/register`, no issuer trust scoring, no rate-limiting. Those are real gaps. They're called out in `PLAN.md`, and the first item in the roadmap is closing them."

> *Brief pause. Land on the calibrated, serious tone — not selling, just stating.*

---

### 🎬 Section 7 — Challenges and lessons (4:45 – 5:10) · face, slightly more reflective

> *Honesty mode. This is where most candidates over-polish. Don't.*

"Two real things tripped me up.

First — **JSON canonicalization between Python and JavaScript** had to be byte-for-byte identical, or the browser-side verification would silently fail. That's a place where copy-paste-from-an-LLM would have broken everything. I rewrote it twice and added unit tests for it.

Second — I had to **resist scope creep constantly**. Every time I solved one layer, I wanted to add the next. The discipline to ship the spine cleanly and *stop* — that was harder than the engineering."

> *Brief pause. Then look up, more forward-leaning.*

---

### 🎬 Section 8 — Where this goes next (5:10 – 5:30) · face, energy lifts

> *Confident but not hype-y.*

"I'm not done with this problem.

In **two weeks**, I'm heading to **SuperAI Singapore** — I've been selected for the hackathon happening **June 8th to 11th**. It's heavily focused on AI agent systems, and I'm planning to evolve this work there into something more ambitious: an agentic layer on top of the NANDA index, where agents don't just *resolve* each other — they *negotiate*, *delegate*, and *audit* each other autonomously.

That's the direction the paper hints at in its future-work section, and I want to be one of the people who actually builds it."

---

### 🎬 Section 9 — Close (5:30 – 5:45) · face, calm, direct

> ***Lower your pace. Look straight into the lens.** This is the line they'll remember.*

"The reason I want this role isn't to maintain a system that already works.

It's because the internet of AI agents is being designed **right now**, in papers and prototypes and hackathons, and I would like to spend the next several years building it carefully.

If that's the kind of person you're looking for, my code is in the repo, my plan is in `PLAN.md`, and I'd love the chance to talk."

> ***Hold the look for two seconds.** Then small natural smile.*

"Thank you."

> *Cut.*

---

## Time budget at a glance

| Section | Window | Length | Mode |
|---|---|---|---|
| 1 — Opening hook | 0:00 – 0:20 | 20 s | Face |
| 2 — Who I am (incl. infra credibility) | 0:20 – 1:00 | 40 s | Voice over UI |
| 3 — The problem | 1:00 – 1:35 | 35 s | Face |
| 4 — Why I built | 1:35 – 2:00 | 25 s | Screen + face cut |
| 5 — Live demo (with VC note) | 2:00 – 3:10 | 70 s | Screen, narrated |
| 6 — How it works (incl. hosting models) | 3:10 – 3:45 | 35 s | Face |
| **6.5 — What I shipped vs cut** | **3:45 – 4:15** | **30 s** | **Face (the move)** |
| **6.7 — Risk model / blast radius** | **4:15 – 4:45** | **30 s** | **Face (serious)** |
| 7 — Challenges | 4:45 – 5:10 | 25 s | Face |
| 8 — SuperAI vision | 5:10 – 5:30 | 20 s | Face |
| 9 — Close | 5:30 – 5:45 | 15 s | Face |
| **Total** | | **5:45** | |

> **If you need to hit a hard 5:00 cap:** drop Section 4 entirely (the "I almost overscoped" beat moves into Section 6.5 implicitly). That saves 25 s and the script lands at 5:20 — close enough.

---

## Shot list

| # | Section | Visual on screen |
|---|---|---|
| 1 | Opening | You only, eye-level, warm |
| 2 | Who I am | UI top of page, you in voiceover |
| 3 | Problem | You, leaning in |
| 4 | Why I built | UI scrolling architecture cards, brief face cut |
| 5 | Demo | UI cascade animating, then tamper section |
| 6 | How it works | You, calmer |
| 6.5 | Shipped vs cut | You, calm and confident |
| **6.7** | **Risk model** | **You, serious — the "VP signal" moment** |
| 7 | Challenges | You, reflective |
| 8 | Vision | You, energy lifting |
| 9 | Close | You, slow and direct |

---

## Pauses and emphasis

### Places to **pause** — don't rush past these

- After *"nobody is treating that as an emergency yet"* (~1:00)
- After the green checks finish animating (~2:45)
- After the red INVALID stamp lands (~3:05) — **one full second**
- After *"defend a small system clearly than a half-finished large one"* (~4:15) — **two seconds**
- After *"by accident or by intent"* (~4:25) — **one full second**, lets the threat-model framing land
- After *"first item in the roadmap is closing them"* (~4:45)
- Before *"Thank you"* (~5:43) — **two full seconds**

### Places to **emphasize** — gentle stress, not volume

- "**we run our own on-premise infrastructure**"
- "**why** I built it the way I did"
- "**in your browser**, using TweetNaCl"
- "**same Ed25519 primitive** that W3C Verifiable Credentials are built on"
- "**deliberately not build**"
- "**real path, not a config flag**"
- "**defend a small system clearly**"
- "**what happens when one malicious agent gets in?**"
- "**contain blast radius**"
- "**by accident *or* by intent**"
- "**two weeks**" (before SuperAI mention)
- "**right now**, in papers and prototypes and hackathons"

---

## Emotional vs technical balance

| Section | Mode | Why |
|---|---|---|
| Opening | Warm + direct | Sets you apart from canned intros |
| Who I am | Grounded, specific | "On-prem infra" line signals you've worked on real systems |
| Problem | Teacher mode | Shows you understand it, not just memorized it |
| Why I built | Slight vulnerability | The "I almost overscoped" line is memorable |
| Demo | Confident, slow | Let visuals do work. Don't over-narrate. |
| How it works | Calm, precise | Proves technical depth without lecturing |
| **What I cut** | **Confident, no apology** | **The single most senior moment in the video** |
| **Risk model** | **Serious, calibrated** | **Engineers who don't think about failure don't get hired as VP** |
| Challenges | Honest, low-key | Separates you from candidates who pretend nothing was hard |
| Vision | Forward-leaning | SuperAI mention is your strongest credibility signal |
| Close | Slow + still | A pause before "thank you" is worth more than 5 extra sentences |

---

## Q&A primer — likely questions, prepared answers

Three questions are most likely after this video. Memorize these short answers — short enough to deliver naturally, specific enough to prove the depth.

### Q1. "Why not real W3C Verifiable Credentials?"

> "Same Ed25519 primitive, same canonical JSON. The VC envelope is a `proof` block wrapped around what I already sign. The brief allowed either, and I prioritized shipping the full chain over shipping a partial envelope. The upgrade is mechanical."

### Q2. "Why is your AgentAddr bigger than 120 bytes?"

> "The paper's 120-byte target reflects the *principle* — records should be lean and stable. My serialized form is around 500 bytes because I inline the public key. In production I'd move the key to a `/keys/{id}` endpoint to hit the byte budget. The architecture doesn't change."

### Q3. "Where's the Adaptive Resolver?"

> "Schema field is there, service isn't. I felt routing logic without a real workload to test it against would be cargo-culting the paper. Standing up a round-robin stub is a 60-minute task — happy to do it on a follow-up if it's on the critical path for the role."

### Bonus Q. "Walk me through the resolution chain."

> "Client hits `/` on the index to get the index's public key. Then `/resolve/{name}` returns a signed AgentAddr containing the agent's public key and pointers to its facts host. Client verifies the AgentAddr signature using the index pubkey. Then fetches the facts URL, gets back an AgentFacts JSON document, verifies its signature using the agent's public key — which it learned in the previous step. Only after both verifications does it use the endpoint."

### Bonus Q. "What stops me from registering a fake agent?"

> "In this MVP, nothing — `/register` is open. That's an honest scope cut. The paper's answer is W3C Verifiable Credentials issued by trusted authorities. In a real deployment you'd require a credential from a recognized issuer for sensitive namespaces, with revocation via VC-Status lists."

### Q4. "What's your threat model? What if one bad agent gets in?"

> "Three layers of containment. First, per-agent keys — compromising one agent doesn't compromise the index. Second, independent signatures at every hop — index, agent, resolver each sign with separate keys, so a compromised facts host can't reroute the chain. Third, short TTLs — even a successful attack has a five-minute window, not forever-in-cache. The paper's §VII trust primitive and the W3C VC-Status revocation list, which is in my roadmap, close the last gap with sub-second revocation. What's not solved yet: Sybil prevention on `/register`, issuer trust scoring, rate limiting. Real gaps, called out in `PLAN.md`."

### Q5. "On hosting — which deployment model would you recommend for an enterprise?"

> "Depends on the regulatory posture. For an enterprise with strict data-residency rules — most banks, government — agent-owned hosting on their own infrastructure is the only viable path; the privacy path then lets external clients resolve without hitting the enterprise network. For a developer-facing product, neutral public hosting via NANDA is the easiest start. For a consortium, federated industry hosting per the paper's §VIII.A.2. The architecture deliberately doesn't force one model — that's its strongest feature, in my opinion."

### Q6. "How would you operationalize this if you got hired tomorrow?"

> "Three things in the first 30 days. One: turn the reference implementation into something we can actually run a public testnet on — sharded KV instead of SQLite, OpenTelemetry traces, a real revocation list. Two: stand up that testnet so external teams have an always-on registry to point their agents at. Three: get one interop demo done with MCP, A2A, or NLWeb. Full plan is in `ROADMAP.md` in the repo — happy to walk through it."

---

## Things deliberately left out

So the video stays believable and you stay defensible:

- ❌ **Public-safety or policing claims.** Would be fabricated for this project; an interviewer would spot it in seconds.
- ❌ **Real-world deployments.** You don't have any *for this project*, and pretending you do is a trap.
- ❌ **Buzzwords.** No "revolutionize," "ecosystem," "leverage," "10x," "game-changing."
- ❌ **Long credentials list.** They have your resume. The video is for personality and judgment.
- ❌ **Asking for the job.** Confidence reads better than asking.

---

## Final advice + submission checklist

### Before you record

- [ ] Read the script out loud **three times**. Mark any spots that feel un-yours and rewrite to your voice.
- [ ] Practice the demo flow **twice**. Know which button you'll click without looking.
- [ ] Run the pre-flight checklist (Section: *Pre-recording setup*).

### While recording

- [ ] **First take is for warmup.** Don't keep it. Do at least 3 takes.
- [ ] Smile slightly at the very start and very end. Resting expressions read as anxious on camera.
- [ ] Don't watch the camera while listening to yourself. Trust the take and move on.
- [ ] If you stumble mid-section, don't start from the top — just pause and restart that section.

### After recording

- [ ] Pick the cleanest take. Don't obsess over playback.
- [ ] Trim head/tail silence so it starts within the first second.
- [ ] Export at 1080p, MP4, audio bitrate ≥ 128 kbps.
- [ ] Upload to Loom (recommended) or YouTube (unlisted). **Don't email a raw file.**
- [ ] Test the link in an incognito window before sending.

### Submission email skeleton

```
To: ashutosh@agenticnet.org
Subject: NANDA VP of Engineering — submission from Swasthika

Hi,

Submitting the NANDA Index challenge.

  • Repo: https://github.com/SwasthikaDev/AiAgent-DNS  (public, 25+ phased commits)
  • Walkthrough video (~5 min): https://www.loom.com/share/[id]
  • Quickstart in README; PLAN.md has scope decisions and explicit non-goals;
    ROADMAP.md is my first-90-days-as-VP-of-Engineering plan.

The short version of what's in there:
  - Lean index + W3C VC v2 AgentFacts (DataIntegrityProof, eddsa-jcs-2022)
  - Dual-host privacy path; Adaptive Resolver (§VI) with signed routing tokens
  - In-browser Ed25519 verification (UI under /ui/) + CLI for technical depth
  - CI on GitHub Actions, Fly.io config ready
  - Three demo agents covering primary, private, and adaptive-routed flows

Happy to walk through any of it live.

Swasthika
[email] · [phone]
```

### One last thing before you hit record

You built the work. The video just lets a human see it. The script above is a scaffold — your job is to make the words sound like *you*. Edit any line that sounds wrong in your voice; the structure matters more than the exact phrasing.

The single most important section is **6.5 — What I shipped, what I cut, why**. Most candidates will hide their cuts. You put them on the table. That is what a VP of Engineering looks like.

You're ready. Go record.
