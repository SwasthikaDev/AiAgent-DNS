"""NANDA client CLI.

This is the headline artifact for the demo. It walks the full chain the
paper describes and prints every signature check, so a reviewer can see
exactly what's being verified and when.

Commands:
  list                          List agents the index knows about.
  resolve <agent_name>          Walk index -> AgentAddr -> AgentFacts, verify all sigs.
  call <agent_name> [--message] Resolve then POST the message to the agent's endpoint.
  demo-tamper <agent_name>      Fetch facts, mutate them, show the client rejecting the sig.
"""

from __future__ import annotations

import json
import os
import sys

# Windows consoles default to cp1252, which can't encode the ✔/→ glyphs this
# CLI prints — that raises UnicodeEncodeError and crashes the command. Force
# UTF-8 on stdout/stderr so the client runs cleanly on a stock Windows shell.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nanda.crypto import (
    did_key_to_pubkey_b64,
    verify_payload,
    verify_vc,
    verify_vc_via_did,
)


INDEX_URL = os.environ.get("INDEX_URL", "http://localhost:8000")

app = typer.Typer(add_completion=False, help="NANDA client — resolve and call agents.")
# emoji=False so technical strings like "did:key:..." aren't mangled into emoji
# (rich would otherwise replace the ":key:" shortcode with 🔑).
console = Console(emoji=False)


def _step(n: int, total: int, msg: str) -> None:
    console.print(f"[bold cyan][{n}/{total}][/bold cyan] {msg}")


def _ok(msg: str) -> None:
    console.print(f"        [green]✔[/green] {msg}")


def _fail(msg: str) -> None:
    console.print(f"        [red]✘ {msg}[/red]")


def _get_index_pubkey() -> str:
    r = httpx.get(f"{INDEX_URL}/", timeout=5.0)
    r.raise_for_status()
    return r.json()["public_key"]


def _resolve_chain(agent_name: str, use_private: bool = False) -> dict:
    """Walk the chain and return {addr, facts, verified} dict.

    Raises typer.Exit on any verification failure.
    """
    total = 5
    _step(1, total, f"Fetching index public key from {INDEX_URL}")
    index_pub = _get_index_pubkey()
    _ok(f"index pubkey: {index_pub[:24]}...")

    _step(2, total, f"Resolving '{agent_name}' at the index")
    r = httpx.get(f"{INDEX_URL}/resolve/{agent_name}", timeout=5.0)
    if r.status_code == 404:
        _fail(f"index has no agent named '{agent_name}'")
        raise typer.Exit(code=2)
    r.raise_for_status()
    addr = r.json()
    _ok(f"got AgentAddr (agent_id={addr['agent_id']})")

    _step(3, total, "Verifying AgentAddr signature against the index public key")
    if not verify_payload(addr, index_pub):
        _fail("AgentAddr signature INVALID — refusing to continue")
        raise typer.Exit(code=2)
    _ok("AgentAddr signature VALID")

    facts_url = addr["private_facts_url"] if use_private and addr.get("private_facts_url") else addr["primary_facts_url"]
    _step(4, total, f"Fetching AgentFacts from {facts_url}")
    r = httpx.get(facts_url, timeout=5.0)
    r.raise_for_status()
    facts = r.json()
    subject = facts.get("credentialSubject", {})
    _ok(f"got AgentFacts VC (label='{subject.get('label')}', cryptosuite={facts.get('proof', {}).get('cryptosuite')})")

    _step(5, total, "Verifying AgentFacts VC against the agent's public key (from AgentAddr)")
    if not verify_vc(facts, addr["public_key"]):
        _fail("AgentFacts VC signature INVALID — refusing to use this endpoint")
        raise typer.Exit(code=2)
    _ok("AgentFacts VC signature VALID (DataIntegrityProof / eddsa-jcs-2022)")

    return {"addr": addr, "facts": facts, "subject": subject}


@app.command(name="list")
def list_agents():
    """Show every agent the index knows about."""
    r = httpx.get(f"{INDEX_URL}/agents", timeout=5.0)
    r.raise_for_status()
    data = r.json()

    table = Table(title=f"Agents in {INDEX_URL}")
    table.add_column("agent_name", style="cyan")
    table.add_column("agent_id", style="dim")
    table.add_column("primary_facts_url")
    table.add_column("private?", justify="center")
    for a in data["agents"]:
        table.add_row(
            a["agent_name"],
            a["agent_id"],
            a["primary_facts_url"],
            "✓" if a["private_facts_url"] else "",
        )
    console.print(table)
    console.print(f"[dim]{data['count']} agent(s) registered[/dim]")


@app.command()
def resolve(
    agent_name: str,
    private: bool = typer.Option(False, "--private", help="Use the private (third-party) facts URL."),
    show_facts: bool = typer.Option(False, "--show-facts", help="Print the full AgentFacts JSON."),
):
    """Resolve an agent: index → AgentAddr → AgentFacts VC, verifying every signature."""
    result = _resolve_chain(agent_name, use_private=private)
    facts = result["facts"]
    subject = result["subject"]
    addr = result["addr"]

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Label", subject["label"])
    summary.add_row("Description", subject["description"])
    summary.add_row("Version", subject["version"])
    summary.add_row("Endpoint", subject["endpoints"]["static"][0])
    summary.add_row("Skills", ", ".join(s["id"] for s in subject["skills"]))
    summary.add_row("Modalities", ", ".join(subject["capabilities"]["modalities"]))
    summary.add_row("VC type", " / ".join(facts.get("type", [])))
    summary.add_row("Cryptosuite", facts.get("proof", {}).get("cryptosuite", "?"))
    summary.add_row("Facts TTL", f"{subject['ttl']}s")
    summary.add_row("Index TTL", f"{addr['ttl']}s")
    console.print()
    console.print(Panel(summary, title="Resolved agent", border_style="green"))

    if show_facts:
        console.print(Panel(json.dumps(facts, indent=2), title="AgentFacts VC (raw)", border_style="dim"))


@app.command()
def call(
    agent_name: str,
    message: str = typer.Option("hello from the client", "--message", "-m"),
    private: bool = typer.Option(False, "--private"),
    adaptive: bool = typer.Option(
        False,
        "--adaptive",
        help="Route via the agent's AdaptiveResolver (§VI). Requires an adaptive_resolver_url in the AgentAddr.",
    ),
    region: str = typer.Option("us-east", "--region", help="Client region hint for adaptive routing."),
):
    """Resolve the agent and POST a message to its endpoint."""
    result = _resolve_chain(agent_name, use_private=private)
    addr = result["addr"]

    if adaptive:
        if not addr.get("adaptive_resolver_url"):
            _fail(f"agent {agent_name} has no adaptive_resolver_url")
            raise typer.Exit(code=2)
        console.print(f"\n[bold]Asking AdaptiveResolver[/bold] {addr['adaptive_resolver_url']}")
        r = httpx.post(
            addr["adaptive_resolver_url"],
            json={
                "agent_name": agent_name,
                "client_region": region,
                "policy": "geo",
            },
            timeout=10.0,
        )
        r.raise_for_status()
        token = r.json()
        # Verify the resolver's signature on the routing token.
        resolver_pub = token.get("resolver_pubkey")
        if not resolver_pub or not verify_payload(token, resolver_pub):
            _fail("AdaptiveResolver token signature INVALID — refusing to route")
            raise typer.Exit(code=2)
        _ok(f"Routing token VALID, expires_at={token['expires_at']}, policy={token['policy_applied']}")
        endpoint = token["endpoint"]
        console.print(f"[bold]Resolver dispatched →[/bold] {endpoint}  ([dim]region={token['region']}[/dim])")
    else:
        endpoint = result["subject"]["endpoints"]["static"][0]
        console.print(f"\n[bold]Calling[/bold] {endpoint}")

    r = httpx.post(endpoint, json={"message": message}, timeout=10.0)
    r.raise_for_status()
    console.print(Panel(json.dumps(r.json(), indent=2), title="Agent response", border_style="cyan"))


@app.command(name="verify-did")
def verify_did(agent_name: str):
    """Verify AgentFacts by resolving the agent's key from its own did:key.

    The paper-faithful path: instead of trusting the public_key copy the index
    hands out, the client recovers the agent's Ed25519 key from the VC's
    verificationMethod (a did:key) and verifies against that.
    """
    _step(1, 4, f"Fetching index public key from {INDEX_URL}")
    index_pub = _get_index_pubkey()
    _ok("got index pubkey")

    _step(2, 4, f"Resolving '{agent_name}' and verifying the AgentAddr")
    addr = httpx.get(f"{INDEX_URL}/resolve/{agent_name}", timeout=5.0).json()
    if not verify_payload(addr, index_pub):
        _fail("AgentAddr signature INVALID")
        raise typer.Exit(code=2)
    _ok("AgentAddr signature VALID")

    _step(3, 4, "Fetching AgentFacts and reading its verificationMethod (did:key)")
    facts = httpx.get(addr["primary_facts_url"], timeout=5.0).json()
    vm = facts.get("proof", {}).get("verificationMethod", "")
    console.print(f"        verificationMethod: [cyan]{vm}[/cyan]")
    try:
        recovered = did_key_to_pubkey_b64(vm)
    except ValueError as e:
        _fail(f"could not resolve did:key ({e}). Re-run scripts/bootstrap.py?")
        raise typer.Exit(code=2)
    _ok(f"recovered agent pubkey from did:key: {recovered[:24]}…")
    matches = recovered == addr.get("public_key")
    console.print(
        f"        matches AgentAddr.public_key: "
        f"{'[green]yes[/green]' if matches else '[yellow]no[/yellow]'}"
    )

    _step(4, 4, "Verifying the VC using ONLY the DID-resolved key")
    if not verify_vc_via_did(facts):
        _fail("AgentFacts VC INVALID")
        raise typer.Exit(code=2)
    _ok("AgentFacts VC VALID — verified without trusting the index's key copy")
    console.print()
    console.print(Panel(
        "[bold green]Paper-faithful key resolution.[/bold green]\n\n"
        "The agent's verify key was decoded straight from its [bold]did:key[/bold]\n"
        "identifier inside the credential. The index never had to be trusted to\n"
        "hand out the right public key — the key travels with the agent's DID.",
        border_style="green",
    ))


@app.command(name="demo-tamper")
def demo_tamper(agent_name: str):
    """Fetch the AgentFacts, mutate a field, and watch the client reject it.

    This is the explicit proof for the brief's "client should be able to detect
    tampering" requirement. We don't need to mutate anything in flight — we
    pretend a man-in-the-middle changed the endpoint, then run the same
    verifier that the `resolve` command uses.
    """
    _step(1, 4, f"Fetching index public key from {INDEX_URL}")
    index_pub = _get_index_pubkey()
    _ok("got index pubkey")

    _step(2, 4, f"Resolving '{agent_name}' at the index")
    addr = httpx.get(f"{INDEX_URL}/resolve/{agent_name}", timeout=5.0).json()
    if not verify_payload(addr, index_pub):
        _fail("AgentAddr already failed sig check — aborting demo")
        raise typer.Exit(code=2)
    _ok("AgentAddr signature VALID")

    _step(3, 4, "Fetching AgentFacts VC and tampering with the endpoint inside credentialSubject")
    facts = httpx.get(addr["primary_facts_url"], timeout=5.0).json()
    original_endpoint = facts["credentialSubject"]["endpoints"]["static"][0]
    facts["credentialSubject"]["endpoints"]["static"][0] = "http://evil.example.com/steal"
    console.print(f"        original endpoint: [dim]{original_endpoint}[/dim]")
    console.print("        tampered endpoint: [red]http://evil.example.com/steal[/red]")

    _step(4, 4, "Re-verifying tampered AgentFacts VC")
    ok = verify_vc(facts, addr["public_key"])
    if ok:
        _fail("BUG: verifier accepted a tampered document — this should never happen")
        raise typer.Exit(code=1)
    _ok("AgentFacts VC INVALID — client refuses to call the evil endpoint")
    console.print()
    console.print(Panel(
        "[bold green]Tamper detection works.[/bold green]\n\n"
        "A man-in-the-middle who swaps the endpoint URL inside the W3C VC's\n"
        "credentialSubject cannot forge a new DataIntegrityProof without the\n"
        "agent's private key. The client re-canonicalises the document\n"
        "(JCS, RFC 8785), runs Ed25519 verify, and rejects the mutation.",
        border_style="green",
    ))


if __name__ == "__main__":
    app()
