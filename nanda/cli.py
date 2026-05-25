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
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nanda.crypto import verify_payload


INDEX_URL = os.environ.get("INDEX_URL", "http://localhost:8000")

app = typer.Typer(add_completion=False, help="NANDA client — resolve and call agents.")
console = Console()


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
    _ok(f"got AgentFacts (label='{facts.get('label')}')")

    _step(5, total, "Verifying AgentFacts signature against the agent's public key (from AgentAddr)")
    if not verify_payload(facts, addr["public_key"]):
        _fail("AgentFacts signature INVALID — refusing to use this endpoint")
        raise typer.Exit(code=2)
    _ok("AgentFacts signature VALID")

    return {"addr": addr, "facts": facts}


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
    """Resolve an agent: index → AgentAddr → AgentFacts, verifying every signature."""
    result = _resolve_chain(agent_name, use_private=private)
    facts = result["facts"]
    addr = result["addr"]

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Label", facts["label"])
    summary.add_row("Description", facts["description"])
    summary.add_row("Version", facts["version"])
    summary.add_row("Endpoint", facts["endpoints"]["static"][0])
    summary.add_row("Skills", ", ".join(s["id"] for s in facts["skills"]))
    summary.add_row("Modalities", ", ".join(facts["capabilities"]["modalities"]))
    summary.add_row("Facts TTL", f"{facts['ttl']}s")
    summary.add_row("Index TTL", f"{addr['ttl']}s")
    console.print()
    console.print(Panel(summary, title="Resolved agent", border_style="green"))

    if show_facts:
        console.print(Panel(json.dumps(facts, indent=2), title="AgentFacts (raw, signed)", border_style="dim"))


@app.command()
def call(
    agent_name: str,
    message: str = typer.Option("hello from the client", "--message", "-m"),
    private: bool = typer.Option(False, "--private"),
):
    """Resolve the agent and POST a message to its endpoint."""
    result = _resolve_chain(agent_name, use_private=private)
    endpoint = result["facts"]["endpoints"]["static"][0]
    console.print(f"\n[bold]Calling[/bold] {endpoint}")
    r = httpx.post(endpoint, json={"message": message}, timeout=10.0)
    r.raise_for_status()
    console.print(Panel(json.dumps(r.json(), indent=2), title="Agent response", border_style="cyan"))


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

    _step(3, 4, "Fetching AgentFacts and tampering with the endpoint")
    facts = httpx.get(addr["primary_facts_url"], timeout=5.0).json()
    original_endpoint = facts["endpoints"]["static"][0]
    facts["endpoints"]["static"][0] = "http://evil.example.com/steal"
    console.print(f"        original endpoint: [dim]{original_endpoint}[/dim]")
    console.print(f"        tampered endpoint: [red]http://evil.example.com/steal[/red]")

    _step(4, 4, "Re-verifying tampered AgentFacts")
    ok = verify_payload(facts, addr["public_key"])
    if ok:
        _fail("BUG: verifier accepted a tampered document — this should never happen")
        raise typer.Exit(code=1)
    _ok("AgentFacts signature INVALID — client refuses to call the evil endpoint")
    console.print()
    console.print(Panel(
        "[bold green]Tamper detection works.[/bold green]\n\n"
        "A man-in-the-middle who swaps the endpoint URL inside a signed\n"
        "AgentFacts cannot forge a new signature without the agent's private\n"
        "key. The client compares the document against the public key it got\n"
        "from the (independently-signed) AgentAddr and rejects the mutation.",
        border_style="green",
    ))


if __name__ == "__main__":
    app()
