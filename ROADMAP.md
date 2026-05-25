# First 90 Days as VP of Engineering — Project NANDA

> A working document, not a manifesto. Written for the Project NANDA / Agentic Net technical leadership hire.
> Premise: the resolution architecture in [`PLAN.md`](./PLAN.md) is the right one. The job is now to turn it into a system the industry can ship against — code, standards, ecosystem, and team — within a year.

---

## How I'd frame the role

> *Project NANDA exists at the intersection of three communities that don't usually talk to each other: the W3C/IETF standards crowd, the AI agent platform builders (MCP, A2A, ANP, LangChain, MS NLWeb), and the enterprise security organizations that will actually run agents in production. The VP of Engineering's first job is to make sure those three groups can build against the same spec without picking sides.*

That belief shapes every decision below.

---

## Operating principles

Five rules I'd operate by from day one. Each is a directional bet, not a slogan.

1. **The reference implementation is a load-bearing artifact**, not a marketing prop. Every spec change must compile and run in the reference repo before it ships. If we can't run it, we shouldn't write it.

2. **Specify less, demonstrate more.** Papers describe; running code disambiguates. When two specs disagree, the one with two interop demos wins. Bias all engineering effort toward producing those demos.

3. **Ship the boring parts first.** The exotic parts of the paper (ZKPs, adaptive resolvers with ML-routed traffic) won't matter if registration, resolution, and revocation aren't dead reliable. Reliability is more credible than novelty.

4. **Standards velocity beats product velocity at this stage.** The single biggest enterprise unlock is "this is a real W3C/IETF thing now." Optimize the calendar around that.

5. **Hire for taste and seriousness over volume.** I'd rather have four people who can hold the whole stack in their head than ten who can each only see their slice. We're building infra; infra teams stay small for longer.

---

## Days 1–30 — Listen, ship the obvious, set the trajectory

### Internal

- **Week 1:** 1:1s with everyone on the technical and research side. Ramesh, Pradyumna, the MIT team, the corporate research partners (Akamai, Cisco, TCS, Dell, HCL, Flower AI). Two questions in every meeting: *what's working, what's blocking you*. No promises in the first week.
- **Week 1–2:** Read every existing repo, every internal RFC, every meeting note. Stand up a private project board so I'm working *with* what's in flight, not parallel to it.
- **Week 2:** Publish an **internal "as-built" doc** — what's actually shipping vs what the paper describes. The honest gap analysis from this MVP, scaled up. (PLAN.md §9 is a small version of this.)
- **Week 3:** Hire the first engineer (see *Hiring*, below). Time-bound — if we don't find someone good, hold.
- **Week 4:** Publish the first public roadmap draft. Internal consensus first, external second.

### External

- **Week 2:** Open NANDA-Index reference repo to the public if it isn't already. Same hygiene as this MVP — phased commits, plan-and-non-goals, demo guide, CI badge, license.
- **Week 3:** Get a Discord or a small community Slack stood up. Not a marketing channel — a developer one.
- **Week 4:** Write a 2,000-word blog post: *"What we shipped vs what's still a sketch."* Honest. Becomes the de facto reference for outsiders trying to evaluate NANDA seriously.

### Technical

- **Promote the MVP into the reference implementation.** Most of what's in this repo (signed AgentAddr, VC-wrapped AgentFacts, dual-host privacy path, adaptive resolver stub) is the spine of the reference. Refactor for production:
  - Replace single-node SQLite with sharded KV (DynamoDB / FoundationDB) behind the same interface
  - Wire OpenTelemetry traces through every service (the paper specifies it; we should ship it)
  - Add a real **VC-Status revocation list** endpoint and client-side check
  - Add **DID resolution** for `did:web` and `did:key` so agents can be identified by their cryptographic identity, not just a URN
- **Stand up a public test net** — `index.testnet.nanda.dev` or similar — so external teams have a free, always-on registry to point their agents at.
- **Define one cross-stack contract test suite** any compliant index, facts host, or client must pass. Publish under MIT.

### What success looks like at day 30

- I know every name, every workstream, every blocker.
- One external blog post has shipped and been linked by someone neutral (not us).
- Reference repo passes its own contract tests in CI.
- One new engineer offered (or honest pass).
- Public testnet has at least 3 external agents registered.

---

## Days 31–60 — Build trust through interoperability

### Internal

- **Hire engineers 2 and 3.** Target profile: people who've shipped infra to enterprises before (CDNs, identity providers, certificate authorities). Senior IC level. No managers yet.
- **Establish a weekly "what shipped, what slipped" ritual.** Public to the company, optional for the world. Two-paragraph format, no slides.
- **Run a private security review** of the reference implementation. Engage a third party (Trail of Bits, NCC Group). Budget ~$25k; the credibility uplift is worth it.
- **Codify on-call.** Even a small team needs a rotation. The reference implementation now runs the public testnet; we have an SLA whether we like it or not.

### External

- **Public RFC for AgentFacts v1.0.** Lock the schema. Solicit comments for 30 days. Aim for IETF Internet-Draft submission by end of Q2.
- **Three interop demos with named partners**, in order of leverage:
  1. **Anthropic MCP** — show a NANDA-resolved agent invoked over MCP. Most strategic; biggest community.
  2. **Google A2A** — embed an A2A Agent Card as a `skills` extension inside an AgentFacts VC. Proves the supersetting story from §V of the paper.
  3. **Microsoft NLWeb** — register an NLWeb agent in the NANDA index. Demonstrates the quilt model with a real second registry.
- **Speak at one event** (AI Engineer Summit, KubeCon, Web3 Identity Week — whichever lands first). Talk on *building the trust layer for the agent web*, not a NANDA puff piece.

### Technical

- **Federated trust zones (§VII.B).** Implement the cross-signing protocol so two independent indexes can recognize each other's issued credentials. Without this, "quilt" is a metaphor; with it, it's a feature.
- **Real adaptive resolver, not a stub.** Move beyond round-robin: latency-aware routing using simple p50/p95 telemetry from the agent endpoints, geo from MaxMind. Stay below 300 LOC; resist the temptation to build a service mesh.
- **VC-Status revocation list with sub-second propagation**, per the paper's §VII.D promise. CRDT-based or pub-sub; the spec is silent, we pick.
- **Performance milestone:** 10k resolves/sec sustained from a single index shard on a $40/mo VM. Publish the benchmark code so others can verify.

### What success looks like at day 60

- Two new engineers shipping code.
- Public RFC posted, getting non-trivial review comments.
- At least one interop demo recorded as a video, embedded in someone else's blog post.
- Security review report in hand; high-severity findings closed; the rest tracked publicly.
- Testnet handling >100 reqs/sec across >10 external agents.

---

## Days 61–90 — Standards, ecosystem, prove the model

### Internal

- **First post-mortem culture moment.** Whatever has gone wrong by now, write the post-mortem in public. Sets the tone better than any onboarding doc.
- **Hire engineer 4 and the first dev-rel person.** At this scale, one good DevRel hire produces more leverage than a fifth engineer.
- **Plan Q3/Q4 with the team, not for them.** Half-day offsite. Output: a one-page priority list everyone agrees with.

### External

- **Submit AgentFacts as an IETF Internet-Draft.** Even if the WG path is long, having a draft I-D in hand changes how enterprises and lawyers talk about NANDA.
- **Start the W3C VC Working Group conversation.** Our `AgentFactsCredential` is a natural addition to the VC ecosystem. Apply for liaison status; attend one face-to-face if scheduling permits.
- **Open governance proposal.** Who decides what goes in the spec? Sketch a steering-committee model with rotating representation from research (MIT), platform vendors (Anthropic, Google, Microsoft), enterprise (Cisco, Akamai), and the open community. Solicit comment.
- **Publish a credible **launch partner program** with 5 named enterprises piloting NANDA in non-production environments by end of year. Even one named pilot is better than five vague intents.

### Technical

- **Production-grade hosting.** Move the testnet from a single Fly machine to a 3-region deployment behind Cloudflare. Real DNS, real TLS, real ops. ~$200/mo, paid out of the company; we are the operator of last resort.
- **First end-to-end agent-to-agent demo.** Two real agents from different orgs, resolving each other through NANDA, negotiating a small transaction, with full audit trail. This is the moment the architecture stops being theoretical for outsiders.
- **Begin work on the agentic layer.** Not as a research project — as a thin SDK that lets developers write `agent.delegate_to("@translator")` and have it Just Work. The agentic future is closer than the standards conversation suggests; we should be ahead of it.

### What success looks like at day 90

- AgentFacts is a published IETF Internet-Draft.
- 4 engineers, 1 DevRel, all shipping.
- 3 interop demos public, ≥2 picked up by external press or partner blogs.
- 5 named enterprise pilots in motion (even if early).
- Reference implementation handles 100k resolves/day in production without manual intervention.
- The conversation in the AI agent community has shifted from "what is NANDA?" to "is your agent NANDA-resolvable?"

---

## Hiring philosophy

Four roles in 90 days. In order:

1. **Senior infrastructure engineer.** Has shipped a CDN, an identity service, or a certificate authority. Comfortable with the boring parts of distributed systems. Reports to me.
2. **Senior protocol engineer.** Has read RFCs for fun. Can defend a spec choice in front of an IETF working group without flinching. Likely has prior W3C VC or DID work.
3. **Senior platform engineer.** Front-end-leaning. Owns the developer experience surface — SDKs, CLI, docs, examples. The reference implementation's UX has to be good or the spec dies.
4. **Developer relations / community.** Writes well, speaks well, codes well enough to be credible. Owns the public face of the project. Not a marketer.

**No engineering managers in the first 90 days.** I manage the team directly while we're under 6 people. Adding a layer too early calcifies the culture before it has a chance to form.

**Hiring bar:** every offer must be unanimous among existing team. No exceptions, even when slow. Wrong hires at this stage cost more than missed quarters.

---

## What I would not do

These look attractive at first. I'd resist them in the first 90 days.

- **Token / crypto economic model.** The paper mentions it as an open question (§XI.H). It's a multi-year governance distraction. Defer past day 90 unless an investor specifically demands it.
- **Building our own LLM-based agents.** We're infrastructure. Stay infrastructure. Building agents would put us in competition with our own customers.
- **Closed-source enterprise tier.** Tempting for revenue. Toxic for trust. Cathedral/bazaar — we're the bazaar, the cathedral can come later.
- **Aggressive marketing.** This community is small and skeptical. One real demo lands more than ten press releases. Run the playbook of Cloudflare and Stripe in their first two years, not the one of the typical AI-agent-vaporware startup.
- **Hiring an engineering manager too early.** Above.

---

## How I'd handle the inevitable hard tradeoffs

A few that I expect to land on my desk in the first quarter:

- **"We need to ship feature X for partner Y by date Z."**
  My default: ask whether the feature belongs in the reference implementation, or in a partner-specific fork. If it's reference-grade, prioritize it and slip something else publicly. If not, help the partner build a fork, keep the reference clean.

- **"Should we accept enterprise contributions even if they're not aligned with the spec?"**
  Yes, with a CLA and a clear "experimental" branch. Better to engage than alienate. But the main branch protects the spec.

- **"Researcher wants to publish a new variant of AgentFacts."**
  Encourage. The paper is V0.3 for a reason. Help them ship the variant as an experimental extension, not a competing schema. Standards bodies hate forks; we should too.

- **"Competitor X (ANS, ANP) is gaining traction."**
  Don't fight. Interoperate. Whichever spec ends up winning, the trust layer (signed VCs over canonical JSON) should be portable. Make sure ours is.

---

## My first 90-day promise to the team

I will:
- Be in every Monday standup unless I'm physically traveling.
- Write the weekly "what shipped, what slipped" personally. Not delegated.
- Read every PR review-worthy in week one. Comment on at least 25% of them.
- Take exactly one week of vacation in the first 90 days. (Pacing matters; burnout is the silent killer of early-stage infra teams.)
- Default to public. Slack threads, decisions, post-mortems — public unless there's a specific reason not to.

I will not:
- Promise headcount we can't fund.
- Promise dates without a confidence level next to them.
- Override an IC's technical judgment publicly.
- Hire anyone the existing team can't enthusiastically endorse.

---

## On India / US time zones

I'm based in India and applying for a US-based role. My plan if hired:

- **Default working hours:** 8pm – 4am IST (roughly 10:30am – 6:30pm ET). Real overlap with US East, full overlap with US West morning.
- **Travel:** quarterly to the US for a week minimum, more if a specific milestone demands it. Open to relocation by end of year if the team is operating predominantly out of one US city.
- **Time-zone discipline:** asynchronous-first writing culture. The reason I default to public Slack / Notion / GitHub is partly that distributed teams die when decisions happen verbally.

I've worked across time zones before. The trick isn't superhuman scheduling — it's ruthlessly writing things down.

---

## Why this role, why now

Because the internet of AI agents is being designed in 2026, not in 2031. The opportunity to be one of the small number of people who shape its trust layer doesn't repeat. Project NANDA is closer to that center than any other group I've evaluated.

If you give me the role, I will spend year one making sure NANDA is the spec other specs interoperate against — not because we won a marketing war, but because the reference implementation, the docs, the tests, and the team are visibly the most serious work in the space.

That's the bet. Let's see if we agree on it.

— [Swasthika]
