"""SQLite layer for the index service.

Single table, no migration framework. The whole point of the lean index is
that it stores almost nothing — keep this file small.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  agent_id              TEXT PRIMARY KEY,
  agent_name            TEXT UNIQUE NOT NULL,
  public_key            TEXT NOT NULL,
  primary_facts_url     TEXT NOT NULL,
  private_facts_url     TEXT,
  adaptive_resolver_url TEXT,
  ttl_seconds           INTEGER NOT NULL DEFAULT 3600,
  registered_at         TEXT NOT NULL
);
"""


class IndexDB:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def insert_agent(
        self,
        *,
        agent_id: str,
        agent_name: str,
        public_key: str,
        primary_facts_url: str,
        private_facts_url: Optional[str],
        adaptive_resolver_url: Optional[str],
        ttl_seconds: int,
        registered_at: str,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO agents
                (agent_id, agent_name, public_key, primary_facts_url,
                 private_facts_url, adaptive_resolver_url, ttl_seconds, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    agent_name,
                    public_key,
                    primary_facts_url,
                    private_facts_url,
                    adaptive_resolver_url,
                    ttl_seconds,
                    registered_at,
                ),
            )

    def get_by_name(self, agent_name: str) -> Optional[sqlite3.Row]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM agents WHERE agent_name = ?", (agent_name,)
            ).fetchone()
        return row

    def list_agents(self) -> list[sqlite3.Row]:
        with self._conn() as c:
            return list(c.execute("SELECT * FROM agents ORDER BY registered_at").fetchall())

    def upsert_agent(self, **kw) -> None:
        """Used by the bootstrap script so it's idempotent across runs."""
        with self._conn() as c:
            c.execute("DELETE FROM agents WHERE agent_name = ?", (kw["agent_name"],))
        self.insert_agent(**kw)
