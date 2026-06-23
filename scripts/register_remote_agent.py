"""Register an agent whose endpoint lives on ANOTHER machine.

Run this on the MAIN laptop (the one with the index + facts host up). It
registers `urn:agent:demo:remote` in the local index, signs its AgentFacts
pointing at the remote endpoint, and publishes them to the primary facts host —
exactly like bootstrap.py, except the endpoint is your other laptop's LAN IP.

Usage (from the repo root):

    python scripts/register_remote_agent.py http://192.168.1.42:9000/echo

Then, from the main laptop, the full verified chain reaches the other machine:

    python -m nanda.cli resolve urn:agent:demo:remote
    python -m nanda.cli call urn:agent:demo:remote -m "hello across the network"

All signing stays here; the remote machine only echoes. The call response
includes the remote host's name, proving it ran on the other laptop.
"""

from __future__ import annotations

import sys

# scripts/ is on sys.path[0] when run as `python scripts/register_remote_agent.py`,
# so we can reuse bootstrap's registration logic directly.
from bootstrap import PRIMARY_FACTS_URL, register_agent


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].startswith("http"):
        print("usage: python scripts/register_remote_agent.py http://<laptop2-ip>:<port>/echo")
        sys.exit(1)

    endpoint = sys.argv[1]

    register_agent(
        agent_name="urn:agent:demo:remote",
        label="Remote Agent (second machine)",
        description="An echo agent hosted on a separate laptop, reached over the LAN.",
        endpoint=endpoint,
        facts_host_url=PRIMARY_FACTS_URL,
        use_private=False,
        skills=[
            {
                "id": "echo",
                "description": "Echoes input — runs on a physically separate machine.",
            }
        ],
        capabilities={
            "modalities": ["text"],
            "streaming": False,
            "authentication": {"methods": ["none"]},
        },
    )

    print()
    print(f"Registered urn:agent:demo:remote -> {endpoint}")
    print("Try it from this laptop:")
    print('  python -m nanda.cli call urn:agent:demo:remote -m "hello across the network"')


if __name__ == "__main__":
    main()
