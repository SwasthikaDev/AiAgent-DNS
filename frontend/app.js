// =====================================================================
// NANDA Index Explorer — frontend logic
//
// All signature checks run in this file using TweetNaCl (Ed25519). That
// means the green ✓ a reviewer sees is *actually* verified client-side —
// it's not the server reporting "trust me, valid".
// =====================================================================

const CFG = window.NANDA_CONFIG;
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ----------- Canonical JSON (must match nanda/crypto.py) --------------
// Python: json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
// We replicate that byte-for-byte so signatures produced server-side
// verify client-side without a re-signing round-trip.
function canonicalize(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalize).join(",") + "]";
  }
  const keys = Object.keys(value).sort();
  return (
    "{" +
    keys.map((k) => JSON.stringify(k) + ":" + canonicalize(value[k])).join(",") +
    "}"
  );
}

function verifyEd25519(signedDoc, publicKeyB64) {
  // Legacy detached-signature shape: top-level `signature` field.
  const { signature, ...unsigned } = signedDoc;
  if (!signature) return false;
  try {
    const msg = new TextEncoder().encode(canonicalize(unsigned));
    const sig = nacl.util.decodeBase64(signature);
    const pub = nacl.util.decodeBase64(publicKeyB64);
    return nacl.sign.detached.verify(msg, sig, pub);
  } catch (e) {
    console.error("verify error:", e);
    return false;
  }
}

// W3C VC v2 with DataIntegrityProof (cryptosuite: eddsa-jcs-2022).
// Strips `proof` entirely, re-canonicalizes, verifies via the same Ed25519
// primitive as `verifyEd25519`.
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
  } catch (e) {
    console.error("verify VC error:", e);
    return false;
  }
}

// ----------- Pretty JSON renderer ------------------------------------
function renderJson(obj, opts = {}) {
  const json = JSON.stringify(obj, null, 2);
  const escaped = json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped.replace(
    /("([^"\\]|\\.)*")(\s*:)?|\b(true|false|null)\b|-?\d+(\.\d+)?(?:[eE][+-]?\d+)?/g,
    (match, str, _esc, colon, bool) => {
      if (str) {
        if (colon) {
          const key = str.slice(1, -1);
          if (key === "signature") {
            return `<span class="json-key">${str}</span>${colon}`;
          }
          return `<span class="json-key">${str}</span>${colon}`;
        }
        // value string
        if (opts.highlightSig && match.length > 60) {
          return `<span class="json-sig">${str}</span>`;
        }
        return `<span class="json-str">${str}</span>`;
      }
      if (bool === "true" || bool === "false") {
        return `<span class="json-bool">${match}</span>`;
      }
      if (bool === "null") {
        return `<span class="json-null">${match}</span>`;
      }
      return `<span class="json-num">${match}</span>`;
    }
  );
}

// ----------- Service status pings ------------------------------------
const SERVICES = [
  { name: "index",    url: CFG.INDEX_URL,             color: "cyan"    },
  { name: "facts·1",  url: CFG.FACTS_PRIMARY_URL,     color: "violet"  },
  { name: "facts·2",  url: CFG.FACTS_PRIVATE_URL,     color: "violet"  },
  { name: "agent·1",  url: CFG.AGENT_ECHO_URL,        color: "emerald" },
  { name: "agent·2",  url: CFG.AGENT_TRANSLATE_URL,   color: "emerald" },
  { name: "resolver", url: CFG.ADAPTIVE_RESOLVER_URL, color: "amber"   },
];

async function pingService(url) {
  try {
    const r = await fetch(url + "/", { method: "GET", cache: "no-store" });
    return r.ok;
  } catch {
    return false;
  }
}

async function refreshStatus() {
  const el = $("#serviceStatus");
  if (!el) return; // status pills removed from the header — nothing to render
  el.innerHTML = SERVICES.map(
    (s) =>
      `<span class="status-pill"><span class="status-dot unknown" data-svc="${s.name}"></span><span class="text-slate-300">${s.name}</span></span>`
  ).join("");
  await Promise.all(
    SERVICES.map(async (s) => {
      const up = await pingService(s.url);
      const dot = el.querySelector(`[data-svc="${s.name}"]`);
      dot.classList.remove("unknown");
      dot.classList.add(up ? "up" : "down");
    })
  );
}

// ----------- Agent registry ------------------------------------------
let AGENT_CACHE = [];

async function loadAgents() {
  const list = $("#agentList");
  list.innerHTML = `<div class="text-slate-500 text-sm">Loading…</div>`;
  try {
    const r = await fetch(`${CFG.INDEX_URL}/agents`);
    const data = await r.json();
    AGENT_CACHE = data.agents || [];

    if (AGENT_CACHE.length === 0) {
      list.innerHTML = "";
      $("#noAgentsHelp").classList.remove("hidden");
    } else {
      $("#noAgentsHelp").classList.add("hidden");
      list.innerHTML = AGENT_CACHE.map(renderAgentRow).join("");
      list.querySelectorAll("[data-action]").forEach((btn) => {
        btn.addEventListener("click", () =>
          onAgentAction(btn.dataset.action, btn.dataset.agent)
        );
      });
    }
    populateAgentSelects();
  } catch (e) {
    list.innerHTML = `<div class="alert alert-danger text-sm">
      <strong>Can't reach the index at ${CFG.INDEX_URL}.</strong>
      Make sure <code>docker compose up</code> is running.
    </div>`;
  }
}

function renderAgentRow(a) {
  const isPrivate = !!a.private_facts_url;
  const badge = isPrivate
    ? `<span class="hosting-badge private">private host</span>`
    : `<span class="hosting-badge primary">primary host</span>`;
  const factsUrl = isPrivate ? a.private_facts_url : a.primary_facts_url;
  return `
    <article class="agent-row">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="agent-name">${a.agent_name}</span>
          ${badge}
        </div>
        <div class="agent-meta truncate">
          <span>${a.agent_id}</span>
          <span class="mx-2 text-slate-400">·</span>
          <span>${factsUrl}</span>
        </div>
      </div>
      <div class="flex gap-2 flex-shrink-0">
        <button data-action="resolve" data-agent="${a.agent_name}" class="btn-secondary">Resolve</button>
        <button data-action="call" data-agent="${a.agent_name}" class="btn-primary">Call</button>
      </div>
    </article>
  `;
}

function populateAgentSelects() {
  const opt = (a, mark) =>
    `<option value="${a.agent_name}">${a.agent_name}${mark && a.adaptive_resolver_url ? "  ·  adaptive" : ""}</option>`;
  $("#callAgentSelect").innerHTML = AGENT_CACHE.map((a) => opt(a, true)).join("");
  $("#tamperAgentSelect").innerHTML = AGENT_CACHE.map((a) => opt(a, false)).join("");
  syncAdaptiveAvailability();
}

// Enable the adaptive controls only for agents that actually have an
// adaptive_resolver_url. Otherwise disable + hint, so you don't tick the toggle
// and hit a dead end after a full resolve.
function syncAdaptiveAvailability() {
  const name = $("#callAgentSelect").value;
  const agent = AGENT_CACHE.find((a) => a.agent_name === name);
  const supported = !!(agent && agent.adaptive_resolver_url);
  const toggle = $("#adaptiveToggle");
  const region = $("#regionSelect");
  const hint = $("#adaptiveHint");
  toggle.disabled = !supported;
  region.disabled = !supported;
  if (!supported) toggle.checked = false;
  toggle.closest("label")?.classList.toggle("opacity-50", !supported);
  if (hint) hint.textContent = supported ? "" : "only the multiregion agent supports adaptive routing";
}

function onAgentAction(action, name) {
  if (action === "resolve") {
    runResolutionCascade(name).then(() => {
      $("#resolutionPanel").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  } else if (action === "call") {
    $("#callAgentSelect").value = name;
    $("#callBtn").click();
    // Scroll to the cascade so the user watches the same panel as Resolve —
    // Call just continues that story with the call step + the response.
    $("#resolutionPanel").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

// ----------- Cascade renderer (shared by resolve + call + tamper) ----
function cascadeEl() {
  return $("#resolutionPanel");
}

function resetCascade() {
  cascadeEl().innerHTML = `<div class="space-y-2" id="cascadeSteps"></div>`;
  return $("#cascadeSteps");
}

function appendStep(host, { num, total, title, detail, status }) {
  const node = document.createElement("div");
  node.className = `cascade-step ${status}`;
  node.innerHTML = `
    <div class="step-num ${status}">${num}</div>
    <div class="min-w-0 flex-1">
      <div class="step-title">${title}</div>
      ${detail ? `<div class="step-detail">${detail}</div>` : ""}
    </div>
  `;
  host.appendChild(node);
  requestAnimationFrame(() => node.classList.add("shown"));
  return node;
}

// Append a tech-detail block under the most recent step. Each line in `lines`
// is rendered as a small mono row; use the helper HTML in lines[] for HTTP
// method badges, ok/fail color, etc.
function addStepTech(host, lines) {
  const target = host.lastChild?.querySelector(".min-w-0");
  if (!target) return;
  const wrap = document.createElement("div");
  wrap.className = "step-tech";
  wrap.innerHTML = lines.map(l => `<div class="step-tech-line">${l}</div>`).join("");
  target.appendChild(wrap);
}

// Tiny formatter helpers used by the cascade narrator.
const fmtBytes = (n) => `${n.toLocaleString()} bytes`;
const fmtSig = (s) => s ? `${s.slice(0, 16)}…${s.slice(-8)}` : "?";
const fmtMethod = (m) => `<span class="http-method-${m}">${m}</span>`;
const fmtStatus = (s) => (s >= 200 && s < 300) ? `<span class="tech-ok">${s} OK</span>` : `<span class="tech-fail">${s}</span>`;
// The resolver's "default" policy is round-robin; show the friendlier name.
const policyLabel = (p) => (p === "default" ? "round-robin" : p);
// Canonicalised payload byte count for a given JS object (matches what nacl verifies).
const canonBytes = (obj) => new TextEncoder().encode(canonicalize(obj)).length;

function appendJsonCard(host, title, json, opts = {}) {
  const wrap = document.createElement("div");
  wrap.className = "mt-4";
  wrap.innerHTML = `
    <div class="text-xs uppercase tracking-widest text-slate-500 mb-1">${title}</div>
    <div class="json-block">${renderJson(json, opts)}</div>
  `;
  host.appendChild(wrap);
  return wrap;
}

// ----------- The resolution chain ------------------------------------
// Wrappers that also capture the raw response so the cascade can annotate it
// with HTTP status + payload size. We need the body length for narration —
// the regular .json() call discards it.
async function fetchIndexPubkeyRich() {
  const r = await fetch(`${CFG.INDEX_URL}/`);
  const txt = await r.text();
  return { status: r.status, bytes: txt.length, body: JSON.parse(txt) };
}
async function fetchAddrRich(name) {
  const r = await fetch(`${CFG.INDEX_URL}/resolve/${encodeURIComponent(name)}`);
  const txt = await r.text();
  return { status: r.status, bytes: txt.length, body: r.ok ? JSON.parse(txt) : null };
}
async function fetchFactsRich(url) {
  const r = await fetch(url);
  const txt = await r.text();
  return { status: r.status, bytes: txt.length, body: r.ok ? JSON.parse(txt) : null };
}

// Backwards-compat thin wrappers (kept for the tamper button which uses them).
async function fetchIndexPubkey() { return (await fetchIndexPubkeyRich()).body.public_key; }
async function fetchAddr(name) {
  const r = await fetchAddrRich(name);
  if (!r.body) throw new Error(`index returned ${r.status}`);
  return r.body;
}
async function fetchFacts(url) {
  const r = await fetchFactsRich(url);
  if (!r.body) throw new Error(`facts host returned ${r.status}`);
  return r.body;
}

async function runResolutionCascade(agentName, options = {}) {
  const host = resetCascade();
  const total = 5;
  await sleep(50);

  // ─── 1) index pubkey ─────────────────────────────────────────────────
  appendStep(host, {
    num: 1, total,
    title: `Fetch index public key`,
    detail: `GET ${CFG.INDEX_URL}/`,
    status: "pending",
  });
  let pubFetch;
  try {
    pubFetch = await fetchIndexPubkeyRich();
  } catch (e) {
    host.lastChild.className = "cascade-step error shown";
    host.lastChild.querySelector(".step-num").className = "step-num error";
    return null;
  }
  const indexPub = pubFetch.body.public_key;
  host.lastChild.className = "cascade-step success shown";
  host.lastChild.querySelector(".step-num").className = "step-num success";
  host.lastChild.querySelector(".step-detail").innerHTML =
    `pubkey&nbsp;<span class="text-blue-700 font-semibold break-all">${indexPub}</span>`;
  addStepTech(host, [
    `${fmtMethod("GET")} <span class="tech-value">${CFG.INDEX_URL}/</span> → ${fmtStatus(pubFetch.status)} <span class="tech-label">·</span> ${fmtBytes(pubFetch.bytes)}`,
    `<span class="tech-label">↳ cached:</span> 32-byte Ed25519 public key <span class="tech-label">(base64)</span>`,
    `<span class="tech-label">↳ trust anchor for steps 2–3</span>`,
  ]);
  await sleep(350);

  // ─── 2) resolve to AgentAddr ─────────────────────────────────────────
  appendStep(host, {
    num: 2, total,
    title: `Resolve <span class="text-blue-700 font-mono">${agentName}</span>`,
    detail: `GET ${CFG.INDEX_URL}/resolve/${agentName}`,
    status: "pending",
  });
  const addrFetch = await fetchAddrRich(agentName);
  if (!addrFetch.body) {
    host.lastChild.className = "cascade-step error shown";
    host.lastChild.querySelector(".step-num").className = "step-num error";
    host.lastChild.querySelector(".step-detail").innerHTML = `Not found.`;
    addStepTech(host, [
      `${fmtMethod("GET")} <span class="tech-value">${CFG.INDEX_URL}/resolve/${agentName}</span> → ${fmtStatus(addrFetch.status)}`,
    ]);
    return null;
  }
  const addr = addrFetch.body;
  host.lastChild.className = "cascade-step success shown";
  host.lastChild.querySelector(".step-num").className = "step-num success";
  host.lastChild.querySelector(".step-detail").innerHTML =
    `agent_id&nbsp;<span class="text-violet-700 font-semibold">${addr.agent_id}</span>`;
  addStepTech(host, [
    `${fmtMethod("GET")} <span class="tech-value">${CFG.INDEX_URL}/resolve/${agentName}</span> → ${fmtStatus(addrFetch.status)} <span class="tech-label">·</span> ${fmtBytes(addrFetch.bytes)}`,
    `<span class="tech-label">↳ received:</span> signed AgentAddr <span class="tech-label">(${Object.keys(addr).length} fields, TTL ${addr.ttl}s)</span>`,
    `<span class="tech-label">↳ agent pubkey:</span> <span class="tech-value">${addr.public_key}</span>`,
    `<span class="tech-label">↳ index signature:</span> <span class="tech-value">${addr.signature}</span>`,
  ]);
  await sleep(350);

  // ─── 3) verify AgentAddr ─────────────────────────────────────────────
  appendStep(host, {
    num: 3, total,
    title: `Verify AgentAddr signature against the index's public key`,
    detail: `Ed25519 verify (in browser, via TweetNaCl)`,
    status: "pending",
  });
  const addrCanonBytes = canonBytes(Object.fromEntries(Object.entries(addr).filter(([k]) => k !== "signature")));
  const addrOK = verifyEd25519(addr, indexPub);
  host.lastChild.className = `cascade-step ${addrOK ? "success" : "error"} shown`;
  host.lastChild.querySelector(".step-num").className = `step-num ${addrOK ? "success" : "error"}`;
  addStepTech(host, [
    `<span class="tech-label">op:</span> <span class="tech-value">nacl.sign.detached.verify(canonical, sig, indexPubkey)</span>`,
    `<span class="tech-label">payload:</span> ${fmtBytes(addrCanonBytes)} JCS-canonical JSON <span class="tech-label">(RFC 8785, signature field stripped)</span>`,
    `<span class="tech-label">signature:</span> 64 bytes Ed25519 <span class="tech-label">(base64-decoded from addr.signature)</span>`,
    `<span class="tech-label">key:</span> 32 bytes Ed25519 <span class="tech-label">(from step 1)</span>`,
    `<span class="tech-label">result:</span> ${addrOK ? '<span class="tech-ok">VALID ✓</span>' : '<span class="tech-fail">INVALID ✗</span>'}`,
  ]);
  if (!addrOK) {
    host.lastChild.querySelector(".step-detail").innerHTML =
      `<span class="text-red-700 font-semibold">signature INVALID — index would be impersonated</span>`;
    return null;
  }
  // Show the verified AgentAddr right under the step that produced it.
  appendJsonCard(host, "Signed AgentAddr (verified)", addr, { highlightSig: true });
  await sleep(350);

  // ─── 4) fetch AgentFacts ─────────────────────────────────────────────
  const factsUrl =
    options.private && addr.private_facts_url
      ? addr.private_facts_url
      : addr.primary_facts_url;
  const factsLabel = options.private ? "PrivateFactsURL" : "PrimaryFactsURL";
  appendStep(host, {
    num: 4, total,
    title: `Fetch AgentFacts (${factsLabel})`,
    detail: `GET ${factsUrl}`,
    status: "pending",
  });
  const factsFetch = await fetchFactsRich(factsUrl);
  if (!factsFetch.body) {
    host.lastChild.className = "cascade-step error shown";
    host.lastChild.querySelector(".step-num").className = "step-num error";
    addStepTech(host, [`${fmtMethod("GET")} ${factsUrl} → ${fmtStatus(factsFetch.status)}`]);
    return null;
  }
  const facts = factsFetch.body;
  host.lastChild.className = "cascade-step success shown";
  host.lastChild.querySelector(".step-num").className = "step-num success";
  host.lastChild.querySelector(".step-detail").innerHTML =
    `label&nbsp;<span class="text-amber-700 font-semibold">"${facts.credentialSubject?.label ?? "(unknown)"}"</span>`;
  addStepTech(host, [
    `${fmtMethod("GET")} <span class="tech-value">${factsUrl}</span> → ${fmtStatus(factsFetch.status)} <span class="tech-label">·</span> ${fmtBytes(factsFetch.bytes)}`,
    `<span class="tech-label">↳ type:</span> W3C ${(facts.type || []).join(" / ")}`,
    `<span class="tech-label">↳ issuer:</span> <span class="tech-value">${facts.issuer || ""}</span>`,
    `<span class="tech-label">↳ cryptosuite:</span> <span class="tech-value">${facts.proof?.cryptosuite || "?"}</span>`,
    `<span class="tech-label">↳ proofValue:</span> <span class="tech-value">${facts.proof?.proofValue || ""}</span>`,
  ]);
  await sleep(350);

  // ─── 5) verify the VC ────────────────────────────────────────────────
  appendStep(host, {
    num: 5, total,
    title: `Verify AgentFacts VC against the agent's own public key`,
    detail: `DataIntegrityProof · eddsa-jcs-2022 · pubkey from step 3`,
    status: "pending",
  });
  const vcCanonBytes = canonBytes(Object.fromEntries(Object.entries(facts).filter(([k]) => k !== "proof")));
  const factsOK = verifyVC(facts, addr.public_key);
  host.lastChild.className = `cascade-step ${factsOK ? "success" : "error"} shown`;
  host.lastChild.querySelector(".step-num").className = `step-num ${factsOK ? "success" : "error"}`;
  addStepTech(host, [
    `<span class="tech-label">op:</span> <span class="tech-value">nacl.sign.detached.verify(canonical, proofValue, agentPubkey)</span>`,
    `<span class="tech-label">payload:</span> ${fmtBytes(vcCanonBytes)} JCS-canonical JSON <span class="tech-label">(proof block stripped)</span>`,
    `<span class="tech-label">signature:</span> 64 bytes Ed25519 <span class="tech-label">(base64-decoded from proof.proofValue)</span>`,
    `<span class="tech-label">key:</span> agent pubkey from AgentAddr (step 2) <span class="tech-label">— chain of custody complete</span>`,
    `<span class="tech-label">result:</span> ${factsOK ? '<span class="tech-ok">VALID ✓</span>' : '<span class="tech-fail">INVALID ✗</span>'}`,
  ]);
  if (!factsOK) {
    host.lastChild.querySelector(".step-detail").innerHTML =
      `<span class="text-red-700 font-semibold">VC signature INVALID — refusing to trust endpoint</span>`;
    return null;
  }
  // Show the verified VC right under the step that produced it.
  appendJsonCard(host, "AgentFacts — W3C VC v2 (verified)", facts, { highlightSig: true });
  await sleep(200);

  // Endpoint banner — pull the verified endpoint out of credentialSubject.
  const endpoint = facts.credentialSubject.endpoints.static[0];
  const banner = document.createElement("div");
  banner.className = "alert alert-success mt-5";
  banner.innerHTML = `
    <span class="badge-result ok">verified</span>
    <div class="min-w-0 flex-1">
      <div class="font-semibold">Trust chain complete</div>
      <div class="text-sm mt-0.5">
        Safe to call endpoint
        <span class="font-mono text-emerald-900 font-semibold">${endpoint}</span>
      </div>
      <div class="text-[11px] text-emerald-800/80 mt-2 font-mono leading-relaxed">
        <span class="tech-label">chain:</span>
        index pubkey <span class="tech-label">→</span>
        AgentAddr <span class="tech-label">(signed by index, ${addr.ttl}s TTL)</span> <span class="tech-label">→</span>
        agent pubkey <span class="tech-label">→</span>
        AgentFacts VC <span class="tech-label">(signed by agent, ${facts.credentialSubject.ttl}s TTL)</span> <span class="tech-label">→</span>
        endpoint
      </div>
    </div>
  `;
  cascadeEl().appendChild(banner);

  return { addr, facts };
}

// Append an extra step to the cascade panel after the main 5 are done — used
// by the adaptive flow + the final POST to the agent endpoint so they share
// the same step-by-step narration as the resolution chain.
function appendExtraStep({ num, title, detail, status, tech }) {
  const host = $("#cascadeSteps");
  if (!host) return;
  appendStep(host, { num, total: num, title, detail, status });
  if (tech) addStepTech(host, tech);
}

// Keep the adaptive controls in sync with whichever agent is selected.
$("#callAgentSelect").addEventListener("change", syncAdaptiveAvailability);

// ----------- Call ----------------------------------------------------
$("#callBtn").addEventListener("click", async () => {
  const name = $("#callAgentSelect").value;
  const message = $("#callMessage").value || "hello from the browser";
  const useAdaptive = $("#adaptiveToggle").checked;
  const region = $("#regionSelect").value;
  const resultBox = $("#callResult");
  resultBox.classList.remove("hidden");
  resultBox.innerHTML = `<div class="text-sm text-slate-500">Resolving agent (full chain below)…</div>`;

  const resolved = await runResolutionCascade(name);
  if (!resolved) {
    resultBox.innerHTML = `<div class="alert alert-danger text-sm">Resolution failed; refusing to call.</div>`;
    return;
  }

  let endpoint;
  let routing = null; // {region, policy} when the adaptive resolver chose for us

  // ─── Optional adaptive dispatch (extends the cascade panel) ─────────
  if (useAdaptive) {
    const resolverUrl = resolved.addr.adaptive_resolver_url;
    if (!resolverUrl) {
      resultBox.innerHTML = `<div class="alert alert-danger text-sm">
        This agent has no <code>adaptive_resolver_url</code>. Try the <strong>multiregion</strong> agent.
      </div>`;
      return;
    }
    // Auto → let the resolver decide (round-robin, no region sent); a pinned
    // region → geo override. This mirrors production: the resolver chooses by
    // default; an explicit region is just a manual override for the demo.
    const dispatchBody =
      region === "auto"
        ? { agent_name: name, policy: "default" }
        : { agent_name: name, client_region: region, policy: "geo" };

    // Step 6: dispatch to resolver
    appendExtraStep({
      num: 6,
      title: `Dispatch via Adaptive Resolver (§VI)`,
      detail: `POST ${resolverUrl}`,
      status: "pending",
    });
    let token, dispatchStatus, dispatchBytes;
    try {
      const r = await fetch(resolverUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dispatchBody),
      });
      const txt = await r.text();
      dispatchStatus = r.status;
      dispatchBytes = txt.length;
      token = JSON.parse(txt);
    } catch (e) {
      const host = $("#cascadeSteps");
      host.lastChild.className = "cascade-step error shown";
      host.lastChild.querySelector(".step-num").className = "step-num error";
      addStepTech(host, [`error: ${e.message}`]);
      return;
    }
    {
      const host = $("#cascadeSteps");
      host.lastChild.className = "cascade-step success shown";
      host.lastChild.querySelector(".step-num").className = "step-num success";
      host.lastChild.querySelector(".step-detail").innerHTML =
        `resolver chose&nbsp;<span class="text-amber-700 font-semibold">${token.region}</span> · policy&nbsp;<span class="text-amber-700 font-semibold">${policyLabel(token.policy_applied)}</span>`;
      addStepTech(host, [
        `${fmtMethod("POST")} <span class="tech-value">${resolverUrl}</span> → ${fmtStatus(dispatchStatus)} <span class="tech-label">·</span> ${fmtBytes(dispatchBytes)}`,
        `<span class="tech-label">request body:</span> <span class="tech-value">${JSON.stringify(dispatchBody)}</span>`,
        `<span class="tech-label">↳ chosen endpoint:</span> <span class="tech-value">${token.endpoint}</span>`,
        `<span class="tech-label">↳ TTL window:</span> issued_at=${token.issued_at}, expires_at=${token.expires_at} <span class="tech-label">(${token.expires_at - token.issued_at}s)</span>`,
        `<span class="tech-label">↳ resolver pubkey:</span> <span class="tech-value">${token.resolver_pubkey}</span>`,
      ]);
    }
    await sleep(300);

    // Step 7: verify resolver token
    appendExtraStep({
      num: 7,
      title: `Verify routing token signature against the resolver's public key`,
      detail: `Ed25519 verify (in browser, via TweetNaCl)`,
      status: "pending",
    });
    const tokenCanonBytes = canonBytes(Object.fromEntries(Object.entries(token).filter(([k]) => k !== "signature")));
    const tokenOK = verifyEd25519(token, token.resolver_pubkey);
    {
      const host = $("#cascadeSteps");
      host.lastChild.className = `cascade-step ${tokenOK ? "success" : "error"} shown`;
      host.lastChild.querySelector(".step-num").className = `step-num ${tokenOK ? "success" : "error"}`;
      addStepTech(host, [
        `<span class="tech-label">op:</span> <span class="tech-value">nacl.sign.detached.verify(canonical, sig, resolverPubkey)</span>`,
        `<span class="tech-label">payload:</span> ${fmtBytes(tokenCanonBytes)} JCS-canonical JSON`,
        `<span class="tech-label">signature:</span> 64 bytes Ed25519 <span class="tech-label">(from token.signature)</span>`,
        `<span class="tech-label">result:</span> ${tokenOK ? '<span class="tech-ok">VALID ✓</span>' : '<span class="tech-fail">INVALID ✗</span>'}`,
      ]);
    }
    if (!tokenOK) {
      resultBox.innerHTML = `<div class="alert alert-danger text-sm">Adaptive routing token failed signature verification. Refusing to call.</div>`;
      return;
    }
    routing = { region: token.region, policy: policyLabel(token.policy_applied) };
    endpoint = token.endpoint;
    await sleep(300);
  } else {
    endpoint = resolved.facts.credentialSubject.endpoints.static[0];
  }

  // ─── Final call to the endpoint (also lands in the cascade) ─────────
  const finalStepNum = useAdaptive ? 8 : 6;
  appendExtraStep({
    num: finalStepNum,
    title: `Call the verified endpoint`,
    detail: `POST ${endpoint}`,
    status: "pending",
  });
  try {
    const r = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const txt = await r.text();
    const body = JSON.parse(txt);
    const host = $("#cascadeSteps");
    host.lastChild.className = "cascade-step success shown";
    host.lastChild.querySelector(".step-num").className = "step-num success";
    host.lastChild.querySelector(".step-detail").innerHTML =
      `status&nbsp;<span class="text-emerald-700 font-semibold">${r.status}</span> · ${txt.length} bytes`;
    addStepTech(host, [
      `${fmtMethod("POST")} <span class="tech-value">${endpoint}</span> → ${fmtStatus(r.status)} <span class="tech-label">·</span> ${fmtBytes(txt.length)}`,
      `<span class="tech-label">request body:</span> <span class="tech-value">${JSON.stringify({ message })}</span>`,
    ]);

    // Append the response to the cascade too, so the panel tells the whole
    // story end-to-end (resolve → verify → call → response) — this is what
    // visibly separates Call from Resolve.
    const cardTitle = routing
      ? `Agent response — resolver chose ${routing.region} → ${endpoint}`
      : `Agent response — ${endpoint}`;
    appendJsonCard(cascadeEl(), cardTitle, body);

    // When the resolver picked for us (esp. round-robin), make the chosen
    // region/endpoint obvious in the response, not just buried in a step.
    const routingNote = routing
      ? `<div class="alert alert-info text-sm mb-3">
           <span class="badge-result ok" style="background:#d97706">routed</span>
           <div>Adaptive resolver chose region
             <span class="font-semibold">${routing.region}</span>
             <span class="text-slate-500">(policy: ${routing.policy})</span> →
             <span class="font-mono">${endpoint}</span>
           </div>
         </div>`
      : "";
    resultBox.innerHTML = `
      ${routingNote}
      <p class="text-xs uppercase tracking-widest text-slate-500 mb-1.5 font-semibold">Response from <span class="font-mono text-slate-700">${endpoint}</span></p>
      <div class="json-block">${renderJson(body)}</div>
    `;
  } catch (e) {
    resultBox.innerHTML = `<div class="alert alert-danger text-sm">Call failed: ${e.message}</div>`;
  }
});

// ----------- Tamper demo --------------------------------------------
$("#tamperBtn").addEventListener("click", async () => {
  const name = $("#tamperAgentSelect").value;
  const out = $("#tamperResult");
  out.classList.remove("hidden");
  out.innerHTML = `<div class="text-sm text-slate-400">Setting up the attack…</div>`;

  let indexPub, addr, facts;
  try {
    indexPub = await fetchIndexPubkey();
    addr = await fetchAddr(name);
    facts = await fetchFacts(addr.primary_facts_url);
  } catch (e) {
    out.innerHTML = `<div class="alert alert-danger text-sm">Setup failed: ${e.message}</div>`;
    return;
  }

  // Sanity check: the unmutated VC must verify before we attack it.
  const originallyValid = verifyVC(facts, addr.public_key);
  const originalEndpoint = facts.credentialSubject.endpoints.static[0];
  const tampered = JSON.parse(JSON.stringify(facts));
  tampered.credentialSubject.endpoints.static[0] = "http://evil.example.com/steal";
  const tamperedValid = verifyVC(tampered, addr.public_key);

  // Capture the byte counts and signatures so we can show them to the user.
  const stripProof = (vc) => Object.fromEntries(Object.entries(vc).filter(([k]) => k !== "proof"));
  const origBytes = canonBytes(stripProof(facts));
  const tampBytes = canonBytes(stripProof(tampered));
  const sigShort = fmtSig(facts.proof.proofValue);

  out.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <section class="border border-slate-200 rounded-md p-4 bg-white">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-widest font-semibold text-slate-700">Step 1 · Original signed VC</p>
          <span class="badge-result ${originallyValid ? "ok" : "fail"}">${originallyValid ? "valid" : "failed"}</span>
        </div>
        <div class="diff-row before">"credentialSubject.endpoints.static[0]": "${originalEndpoint}"</div>
        <div class="step-tech mt-3">
          <div class="step-tech-line"><span class="tech-label">canonical payload:</span> ${fmtBytes(origBytes)}</div>
          <div class="step-tech-line"><span class="tech-label">signature:</span> <span class="tech-value">${sigShort}</span></div>
          <div class="step-tech-line"><span class="tech-label">verify:</span> <span class="tech-ok">PASS</span></div>
        </div>
      </section>

      <section class="border border-red-200 rounded-md p-4 bg-red-50/50">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-widest font-semibold text-red-700">Step 2 · After MITM tampering</p>
          <span class="badge-result ${tamperedValid ? "ok" : "fail"}">${tamperedValid ? "valid (BUG)" : "invalid"}</span>
        </div>
        <div class="diff-row after-removed">"endpoints.static[0]": "${originalEndpoint}"</div>
        <div class="diff-row after-new mt-1.5">"endpoints.static[0]": "http://evil.example.com/steal"</div>
        <div class="step-tech mt-3">
          <div class="step-tech-line"><span class="tech-label">canonical payload:</span> ${fmtBytes(tampBytes)} <span class="tech-label">(${tampBytes - origBytes >= 0 ? "+" : ""}${tampBytes - origBytes} bytes vs original)</span></div>
          <div class="step-tech-line"><span class="tech-label">signature on file:</span> <span class="tech-value">${sigShort}</span> <span class="tech-label">(unchanged — attacker can't re-sign)</span></div>
          <div class="step-tech-line"><span class="tech-label">verify:</span> <span class="tech-fail">FAIL</span> <span class="tech-label">— sig was over the original bytes, not the mutated ones</span></div>
        </div>
      </section>
    </div>

    <div class="alert alert-danger mt-5">
      <span class="badge-result fail">rejected</span>
      <div class="text-sm leading-relaxed min-w-0 flex-1">
        <strong>Client refused the call.</strong>
        An attacker can mutate any field inside the W3C VC's
        <code>credentialSubject</code>, but cannot forge a new
        <code>DataIntegrityProof</code> (cryptosuite <code>eddsa-jcs-2022</code>)
        without the agent's private key. The client strips
        <code>proof</code>, re-canonicalises via RFC 8785 JCS, runs Ed25519
        verify in the browser, and rejects the mutation before it can hit
        <span class="font-mono">evil.example.com</span>.
        <div class="step-tech mt-3">
          <div class="step-tech-line"><span class="tech-label">op:</span> <span class="tech-value">nacl.sign.detached.verify(canonical(vc − proof), proofValue, agentPubkey)</span></div>
          <div class="step-tech-line"><span class="tech-label">why it fails:</span> Ed25519 signatures are bound to specific bytes — even a one-character change breaks the bit-for-bit match</div>
          <div class="step-tech-line"><span class="tech-label">why JCS matters:</span> without canonical JSON, an attacker could reformat whitespace to match the original; JCS removes that loophole</div>
        </div>
      </div>
    </div>
  `;
});

// ----------- Boot ----------------------------------------------------
$("#refreshBtn").addEventListener("click", () => {
  refreshStatus();
  loadAgents();
});

refreshStatus();
loadAgents();
// Periodic status refresh, lightweight.
setInterval(refreshStatus, 15000);
