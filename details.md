Technical Challenge — VP of Engineering
Foundation for Agentic Networks · Project NANDA
Deadline: May 27th, 2026  Submit to: ashutosh@agenticnet.org

THE BRIEF
Read the NANDA Index paper: Beyond DNS: Unlocking the Internet of AI Agents via the NANDA Index and Verified AgentFacts — arxiv.org/pdf/2507.14263
Build a working prototype that demonstrates the core ideas. We want to see software that runs, not architecture that is described. The scope is intentionally open.
SCOPE
Level 1 — Required
Make it work end-to-end
A client should be able to resolve an agent name and receive something it can verify and act on. The paper's core flow — index → AgentAddr → AgentFacts — should be visible in your code. Register at least two agents, resolve them as a client, and demonstrate the full path from name lookup through metadata retrieval.
On verification: signed JSON, W3C Verifiable Credentials, or another approach of your choice — but the client should be able to detect tampering. Selecting the right point on this spectrum is part of the exercise.
On agent count: two is a floor, not a target. Demonstrate the resolution flow at least twice. Mixing registration types (NANDA-native, enterprise-routed, DID-based) belong in Level 2, not Level 1.

Level 2 — Optional · Bonus
Extend the system
If time permits, extend the prototype. A second component, a different registration type, a way to visualize what is happening, a test harness, or a CLI tool — anything that demonstrates continued momentum rather than additional polish. Level 1 should work end-to-end before Level 2 begins, but functional is the bar, not polished.
DELIVERABLES
Code — A Git repository with full commit history (please do not squash). We would like to see how the work progressed across the 4 days.
A way to run it — a runnable script, docker-compose up, or a short Loom (under 5 minutes) if neither is practical. Running software is the primary artifact.
A short README — sufficient to clone, run, and understand the project. A design document is not required, but a few lines on next steps or scope you set aside is welcome. The remaining tradeoffs can be discussed in the next interview.
GROUND RULES
Any language, framework, or libraries. Use what you would use professionally. Cryptography libraries are encouraged — please use established libraries rather than implementing primitives yourself.
AI coding tools are expected. Use Claude, Copilot, Cursor, or whichever tools you typically use. A brief note in the README on how you used them is helpful for context on your workflow, not evaluation.




HOW TO SUBMIT 
Email ashutosh@agenticnet.org with:
Link to your Git repository (public) 
Link to your Loom, if applicable 
One or two lines on what's in the repo 
We acknowledge receipt within 24 hours. If you do not hear from us, please resend.
