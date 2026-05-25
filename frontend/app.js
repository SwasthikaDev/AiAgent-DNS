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
  { name: "index",   url: CFG.INDEX_URL,          color: "cyan"    },
  { name: "facts·1", url: CFG.FACTS_PRIMARY_URL,  color: "violet"  },
  { name: "facts·2", url: CFG.FACTS_PRIVATE_URL,  color: "violet"  },
  { name: "agent·1", url: CFG.AGENT_ECHO_URL,     color: "emerald" },
  { name: "agent·2", url: CFG.AGENT_TRANSLATE_URL,color: "emerald" },
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
  const opts = AGENT_CACHE.map(
    (a) => `<option value="${a.agent_name}">${a.agent_name}</option>`
  ).join("");
  $("#callAgentSelect").innerHTML = opts;
  $("#tamperAgentSelect").innerHTML = opts;
}

function onAgentAction(action, name) {
  if (action === "resolve") {
    runResolutionCascade(name).then(() => {
      $("#resolutionPanel").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  } else if (action === "call") {
    $("#callAgentSelect").value = name;
    $("#callBtn").click();
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
    <div class="step-num ${status}">${
      status === "success" ? "✓" : status === "error" ? "✗" : num
    }</div>
    <div class="min-w-0 flex-1">
      <div class="step-title">${title}</div>
      ${detail ? `<div class="step-detail">${detail}</div>` : ""}
    </div>
  `;
  host.appendChild(node);
  requestAnimationFrame(() => node.classList.add("shown"));
  return node;
}

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
async function fetchIndexPubkey() {
  const r = await fetch(`${CFG.INDEX_URL}/`);
  return (await r.json()).public_key;
}

async function fetchAddr(name) {
  const r = await fetch(`${CFG.INDEX_URL}/resolve/${encodeURIComponent(name)}`);
  if (!r.ok) throw new Error(`index returned ${r.status}`);
  return r.json();
}

async function fetchFacts(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`facts host returned ${r.status}`);
  return r.json();
}

async function runResolutionCascade(agentName, options = {}) {
  const host = resetCascade();
  const total = 5;
  await sleep(50);

  // 1) index pubkey
  appendStep(host, {
    num: 1, total,
    title: `Fetch index public key`,
    detail: `GET ${CFG.INDEX_URL}/`,
    status: "pending",
  });
  let indexPub;
  try {
    indexPub = await fetchIndexPubkey();
  } catch (e) {
    host.lastChild.className = "cascade-step error shown";
    host.lastChild.querySelector(".step-num").className = "step-num error";
    return null;
  }
  host.lastChild.className = "cascade-step success shown";
  host.lastChild.querySelector(".step-num").className = "step-num success";
  host.lastChild.querySelector(".step-num").textContent = "✓";
  host.lastChild.querySelector(".step-detail").innerHTML =
    `pubkey&nbsp;<span class="text-blue-700 font-semibold">${indexPub.slice(0, 28)}…</span>`;
  await sleep(350);

  // 2) resolve to AgentAddr
  appendStep(host, {
    num: 2, total,
    title: `Resolve <span class="text-blue-700 font-mono">${agentName}</span>`,
    detail: `GET ${CFG.INDEX_URL}/resolve/${agentName}`,
    status: "pending",
  });
  let addr;
  try {
    addr = await fetchAddr(agentName);
  } catch (e) {
    host.lastChild.className = "cascade-step error shown";
    host.lastChild.querySelector(".step-num").className = "step-num error";
    host.lastChild.querySelector(".step-num").textContent = "✗";
    host.lastChild.querySelector(".step-detail").innerHTML = `Not found.`;
    return null;
  }
  host.lastChild.className = "cascade-step success shown";
  host.lastChild.querySelector(".step-num").className = "step-num success";
  host.lastChild.querySelector(".step-num").textContent = "✓";
  host.lastChild.querySelector(".step-detail").innerHTML =
    `agent_id&nbsp;<span class="text-violet-700 font-semibold">${addr.agent_id}</span>`;
  await sleep(350);

  // 3) verify AgentAddr
  appendStep(host, {
    num: 3, total,
    title: `Verify AgentAddr signature against the index's public key`,
    detail: `Ed25519 verify (in browser, via TweetNaCl)`,
    status: "pending",
  });
  const addrOK = verifyEd25519(addr, indexPub);
  host.lastChild.className = `cascade-step ${addrOK ? "success" : "error"} shown`;
  host.lastChild.querySelector(".step-num").className = `step-num ${addrOK ? "success" : "error"}`;
  host.lastChild.querySelector(".step-num").textContent = addrOK ? "✓" : "✗";
  if (!addrOK) {
    host.lastChild.querySelector(".step-detail").innerHTML =
      `<span class="text-red-700 font-semibold">signature INVALID — index would be impersonated</span>`;
    return null;
  }
  await sleep(350);

  // 4) fetch facts (decide which URL based on options.private)
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
  let facts;
  try {
    facts = await fetchFacts(factsUrl);
  } catch (e) {
    host.lastChild.className = "cascade-step error shown";
    host.lastChild.querySelector(".step-num").className = "step-num error";
    host.lastChild.querySelector(".step-num").textContent = "✗";
    return null;
  }
  host.lastChild.className = "cascade-step success shown";
  host.lastChild.querySelector(".step-num").className = "step-num success";
  host.lastChild.querySelector(".step-num").textContent = "✓";
  host.lastChild.querySelector(".step-detail").innerHTML =
    `label&nbsp;<span class="text-amber-700 font-semibold">"${facts.label}"</span>`;
  await sleep(350);

  // 5) verify AgentFacts with the agent's public key (from AgentAddr)
  appendStep(host, {
    num: 5, total,
    title: `Verify AgentFacts signature against the agent's own public key`,
    detail: `pubkey trust anchored by step 3 — chain of custody complete`,
    status: "pending",
  });
  const factsOK = verifyEd25519(facts, addr.public_key);
  host.lastChild.className = `cascade-step ${factsOK ? "success" : "error"} shown`;
  host.lastChild.querySelector(".step-num").className = `step-num ${factsOK ? "success" : "error"}`;
  host.lastChild.querySelector(".step-num").textContent = factsOK ? "✓" : "✗";
  if (!factsOK) {
    host.lastChild.querySelector(".step-detail").innerHTML =
      `<span class="text-red-700 font-semibold">facts signature INVALID — refusing to trust endpoint</span>`;
    return null;
  }
  await sleep(200);

  // Show the resolved docs
  appendJsonCard(cascadeEl(), "Signed AgentAddr (verified)", addr, {
    highlightSig: true,
  });
  appendJsonCard(cascadeEl(), "Signed AgentFacts (verified)", facts, {
    highlightSig: true,
  });

  // Endpoint banner
  const banner = document.createElement("div");
  banner.className = "alert alert-success mt-5";
  banner.innerHTML = `
    <span class="badge-result ok">verified</span>
    <div>
      <div class="font-semibold">Trust chain complete</div>
      <div class="text-sm mt-0.5">
        Safe to call endpoint
        <span class="font-mono text-emerald-900 font-semibold">${facts.endpoints.static[0]}</span>
      </div>
    </div>
  `;
  cascadeEl().appendChild(banner);

  return { addr, facts };
}

// ----------- Call ----------------------------------------------------
$("#callBtn").addEventListener("click", async () => {
  const name = $("#callAgentSelect").value;
  const message = $("#callMessage").value || "hello from the browser";
  const resultBox = $("#callResult");
  resultBox.classList.remove("hidden");
  resultBox.innerHTML = `<div class="text-sm text-slate-500">Resolving agent…</div>`;

  const resolved = await runResolutionCascade(name);
  if (!resolved) {
    resultBox.innerHTML = `<div class="alert alert-danger text-sm">Resolution failed; refusing to call.</div>`;
    return;
  }
  const endpoint = resolved.facts.endpoints.static[0];

  resultBox.innerHTML = `<div class="text-sm text-slate-500">POST ${endpoint} …</div>`;
  try {
    const r = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const body = await r.json();
    resultBox.innerHTML = `
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

  // Sanity: original must verify (proves the system works before we attack it)
  const originallyValid = verifyEd25519(facts, addr.public_key);
  const originalEndpoint = facts.endpoints.static[0];
  const tampered = JSON.parse(JSON.stringify(facts));
  tampered.endpoints.static[0] = "http://evil.example.com/steal";
  const tamperedValid = verifyEd25519(tampered, addr.public_key);

  out.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <section class="border border-slate-200 rounded-md p-4 bg-white">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-widest font-semibold text-slate-700">Step 1 · Original signed facts</p>
          <span class="badge-result ${originallyValid ? "ok" : "fail"}">${originallyValid ? "valid" : "failed"}</span>
        </div>
        <div class="diff-row before">"endpoints.static[0]": "${originalEndpoint}"</div>
      </section>

      <section class="border border-red-200 rounded-md p-4 bg-red-50/50">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs uppercase tracking-widest font-semibold text-red-700">Step 2 · After MITM tampering</p>
          <span class="badge-result ${tamperedValid ? "ok" : "fail"}">${tamperedValid ? "valid (BUG)" : "invalid"}</span>
        </div>
        <div class="diff-row after-removed">"endpoints.static[0]": "${originalEndpoint}"</div>
        <div class="diff-row after-new mt-1.5">"endpoints.static[0]": "http://evil.example.com/steal"</div>
      </section>
    </div>

    <div class="alert alert-danger mt-5">
      <span class="badge-result fail">rejected</span>
      <div class="text-sm leading-relaxed">
        <strong>Client refused the call.</strong>
        An attacker can mutate any field in the JSON, but cannot forge a new
        Ed25519 signature without the agent's private key. The client
        re-canonicalises the mutated document, runs
        <code>nacl.sign.detached.verify</code> in the browser, and rejects it
        before it can hit
        <span class="font-mono">evil.example.com</span>.
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
