# ROADMAP — first 90 days as VP of Engineering at Project NANDA

This is what I'd want to do if I get the role. It's a draft. Plenty of it will change once I've actually met the team and read the code.

---

## A few things I think going in

Not principles, just opinions I currently hold and would defend until someone shows me I'm wrong.

- The reference implementation is the spec. Papers describe; running code resolves ambiguity. When two specs disagree, the one with two interop demos wins. Most of our engineering time should go into making sure those demos exist.

- Ship the boring parts first. What makes infrastructure trusted is mostly uninteresting work — uptime, revocation, observability, docs that don't go stale. The exciting stuff in the paper (ZKPs, ML-routed resolvers) won't matter if registration and resolution aren't reliable.

- Standards velocity probably beats product velocity right now. A published W3C draft unlocks more enterprise conversations than ten new features.

- Keep the team small for longer than feels comfortable. Four people who hold the whole stack in their head will move faster than ten who each see a slice.

---

## Days 1–30 — listen first, ship a couple of obvious things

**Week 1.** 1:1s with everyone. Ramesh, Pradyumna, the MIT team, the partner researchers at Akamai, Cisco, TCS, Dell, HCL, Flower AI. Same two questions in every meeting: what's working, what's stuck. No promises in week one.

**Week 1–2.** Read every internal RFC and every repo. Don't refactor anything until I've understood what's there and why.

**Week 2.** Write an internal "as-built vs as-described" doc — what's actually shipping today vs what the paper claims. This is the basis for everything that comes after.

**Week 3.** Start hiring (more below). Time-boxed. If we don't find someone good, we hold.

**Week 4.** First public roadmap draft. Internal alignment first.

On the engineering side, by end of month one:

- Take what's in this MVP — the lean index, the W3C VC envelope, the adaptive resolver, the dual-host privacy path — and turn it into something we can actually run as a public testnet. Swap SQLite for a real KV store. Wire OpenTelemetry through every service. Add a working revocation list.
- Stand up `index.testnet.nanda.dev`. Free, always-on, so external builders have something to point at instead of `localhost`.
- Write a contract test suite that any compliant index, facts host, or client has to pass. Publish it under MIT.

What done looks like at day 30:
- I know everyone, every workstream, every blocker.
- One honest blog post is out and has been linked by someone who isn't us.
- One new engineer offered, or an honest pass.
- The testnet has at least 3 external agents registered.

---

## Days 31–60 — build trust through interoperability

Hire two more engineers. Senior people who've shipped infra to enterprises — CDNs, identity providers, certificate authorities. People who've been on-call for things that mattered.

Run a private security review of the reference implementation. Probably Trail of Bits or NCC Group. Around $25k. Worth it for the credibility, not just the findings.

Make on-call real. Even a small team needs a rotation once something external depends on it.

On the external side, by end of month two:

- Public RFC for AgentFacts v1.0. 30 days for comments. Aim for IETF Internet-Draft submission by end of Q2.
- Three interop demos with named partners, in this order:
  1. **Anthropic MCP** — a NANDA-resolved agent invoked over MCP. Highest leverage, biggest community.
  2. **Google A2A** — embed an A2A Agent Card as a `skills` extension inside an AgentFacts VC.
  3. **Microsoft NLWeb** — register an NLWeb agent in the NANDA index.

Speaking at one event. AI Engineer Summit, KubeCon, Web3 Identity Week — whichever lands first. Talk should be on building the trust layer for agents, not a NANDA puff piece.

Engineering work this stretch:

- Federation between independent NANDA indexes. Without this, "quilt" is a metaphor. With it, it's a feature.
- The adaptive resolver gets real routing logic — latency-aware p50/p95 telemetry, geo via MaxMind. Should stay under a few hundred lines.
- VC-Status revocation list with sub-second propagation.
- A real performance milestone: 10k resolves/sec sustained from a single index shard on a small VM. Publish the benchmark so others can verify.

---

## Days 61–90 — standards, ecosystem, prove the model

Hire engineer 4 and the first DevRel person. At this scale, one good DevRel hire probably gets more done than a fifth engineer.

Submit AgentFacts as an IETF Internet-Draft. Even if the working-group path is long, having a published I-D in hand changes how enterprises talk about NANDA.

Open the W3C VC Working Group conversation. Apply for liaison status. Our `AgentFactsCredential` is a natural addition to the VC ecosystem.

Open governance proposal. Who decides what goes in the spec? Sketch a steering-committee model with rotating representation: research (MIT), platforms (Anthropic, Google, Microsoft), enterprise (Cisco, Akamai), open community.

A first launch-partner program. Five named enterprises piloting NANDA in non-production by end of year. One real named pilot is worth more than five vague intents.

Engineering:

- Move the testnet from a single VM to a 3-region setup behind Cloudflare. Real DNS, real TLS. Around $200/month, paid by the company. We are the operator of last resort.
- First real agent-to-agent demo. Two agents from different orgs, resolving each other through NANDA, negotiating a small transaction, with a full audit trail. The point at which the architecture stops being theoretical to outsiders.
- Start the agentic-layer SDK. A thin wrapper that lets developers write `agent.delegate_to("@translator")` and have it work.

---

## On hiring

Four roles in 90 days. In order:

1. **Senior infrastructure engineer.** Has shipped a CDN, an identity service, or a CA. Comfortable with the boring parts of distributed systems.
2. **Senior protocol engineer.** Has read RFCs for fun. Can defend a spec choice in an IETF working group. Probably has prior W3C VC or DID work.
3. **Senior platform engineer.** Front-end-leaning. Owns the developer experience — SDKs, CLI, docs, examples.
4. **Developer relations / community.** Writes well, speaks well, codes well enough to be credible. Not a marketer.

No engineering managers in the first 90 days. I'd manage the team directly while we're under six. Adding a layer too early hardens the culture before it's had a chance to form.

Every offer has to be unanimous with the existing team. Even when it's slow. Bad hires at this stage cost more than missed quarters.

---

## Things I'd hold off on

- A token or crypto-economic model. The paper flags it as open. It's a multi-year governance distraction. Defer unless an investor pushes hard.
- Building our own LLM-based agents. We're infrastructure. Building agents puts us in competition with our own customers.
- A closed-source enterprise tier. Tempting for revenue. Bad for trust at this stage.
- Aggressive marketing. This community is small and skeptical. One real demo lands harder than ten press releases.

---

## How I'd handle the hard calls

A few I expect to land on my desk in the first quarter:

**"We need feature X for partner Y by date Z."** First question: does it belong in the reference implementation, or in a partner-specific fork? If it's reference-grade, prioritize it and slip something else publicly. If it's not, help the partner build a fork. Keep the reference clean.

**"Should we accept enterprise contributions that aren't aligned with the spec?"** Yes, with a CLA and a clear "experimental" branch. Better to engage than alienate. The main branch protects the spec.

**"Researcher wants to publish a new variant of AgentFacts."** Encourage. The paper is V0.3 for a reason. Help them ship the variant as an experimental extension, not a competing schema. Standards bodies hate forks; we should too.

**"Competitor X (ANS, ANP) is gaining traction."** Don't fight. Interoperate. Whichever spec wins, the trust layer (signed VCs over canonical JSON) should be portable. Make sure ours is.

---

## What I'd commit to the team

- In every Monday standup unless I'm traveling.
- Write the weekly "what shipped, what slipped" personally. Not delegated.
- Read every PR worth reviewing in week one. Comment on at least 25% of them.
- One week off in the first 90 days. Pacing matters; burnout is the quiet killer of early infra teams.
- Default public. Slack threads, decisions, post-mortems — public unless there's a specific reason not to.

What I wouldn't do: promise headcount we can't fund, promise dates without a confidence level, override an IC's technical judgment publicly, hire anyone the team can't enthusiastically endorse.

---

## On geography

I'm based in India. The role is US-based.

- Default working hours: about 10:30am – 6:30pm ET. Real overlap with US East, full overlap with US West mornings.
- Travel: quarterly to the US for at least a week. More for specific milestones.
- Open to relocation by end of year if the team ends up clustered in one US city.

I've worked across time zones before. The trick isn't superhuman scheduling. It's writing things down.

---

## Why this role

The internet of AI agents is being designed in 2026, not 2031. The chance to be one of the small number of people who shape its trust layer doesn't come around again. Project NANDA is closer to that center than any other group I've looked at.

If you give me the role, year one is about making NANDA the spec other specs interoperate against. Not by winning a marketing war, but because the reference implementation, the docs, the tests, and the team are visibly the most serious work in the space.

That's the goal. Let's see if we agree on it.

— Swasthika
