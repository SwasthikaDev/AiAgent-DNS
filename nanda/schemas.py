"""Pydantic models for the wire protocol.

These define what travels between the index, the facts hosts, the agents,
and the client. They mirror the paper's AgentAddr (§IV) and AgentFacts
(Appendix), trimmed to the fields the MVP actually uses.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------- Index registration ----------


class RegisterRequest(BaseModel):
    """Body of POST /register on the index service."""

    agent_name: str = Field(..., description="URN, e.g. urn:agent:demo:echo")
    public_key: str = Field(..., description="base64 Ed25519 public key of the agent")
    primary_facts_url: str
    private_facts_url: Optional[str] = None
    adaptive_resolver_url: Optional[str] = None
    ttl: int = 3600


# ---------- AgentAddr (returned by index resolve) ----------


class AgentAddr(BaseModel):
    """The lean, signed pointer record returned by the index.

    Equivalent to §IV in the paper.
    """

    agent_id: str
    agent_name: str
    public_key: str
    primary_facts_url: str
    private_facts_url: Optional[str] = None
    adaptive_resolver_url: Optional[str] = None
    ttl: int
    issued_at: str
    signature: str


# ---------- AgentFacts (returned by facts host) ----------


class Provider(BaseModel):
    name: str
    url: str


class Endpoints(BaseModel):
    static: list[str] = Field(default_factory=list)


class Authentication(BaseModel):
    methods: list[str] = Field(default_factory=lambda: ["none"])


class Capabilities(BaseModel):
    modalities: list[str] = Field(default_factory=list)
    streaming: bool = False
    authentication: Authentication = Field(default_factory=Authentication)


class Skill(BaseModel):
    id: str
    description: str


class AgentFacts(BaseModel):
    """Signed JSON document with the agent's capabilities + endpoints.

    Equivalent to the paper's AgentFacts (§V + Appendix), MVP-trimmed.
    """

    id: str
    agent_name: str
    label: str
    description: str
    version: str
    provider: Provider
    endpoints: Endpoints
    capabilities: Capabilities
    skills: list[Skill] = Field(default_factory=list)
    ttl: int = 300
    issued_at: str
    signature: str
