"""AgentCard model, builder, and schema validator (T017).

Implements the discovery document published at
``/.well-known/agent-card.json`` per ``data-model.md`` § AgentCard. The
authoritative wire-format is the JSON Schema fragment in
``specs/001-a2a-bridge/contracts/agent-card.schema.json`` — the Pydantic
model here mirrors that schema and ``validate_against_schema`` re-checks it
at adapter startup so any drift between the model and the schema is caught
before the adapter accepts traffic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import jsonschema
from pydantic import BaseModel, ConfigDict


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    input_modes: list[Literal["text/plain", "text/markdown"]]
    output_modes: list[Literal["text/plain", "text/markdown"]]


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    streaming: Literal[True] = True
    push_notifications: Literal[False] = False
    state_history: Literal[False] = False


class Authentication(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schemes: list[Literal["bearer"]] = ["bearer"]


class AgentCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    url: str
    version: str
    protocols: list[Literal["json-rpc-2.0"]]
    capabilities: Capabilities
    authentication: Authentication
    skills: list[Skill]


_SCHEMA: dict | None = None


def _schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[5]
        / "specs"
        / "001-a2a-bridge"
        / "contracts"
        / "agent-card.schema.json"
    )


def _load_schema() -> dict:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(_schema_path().read_text(encoding="utf-8"))
    return _SCHEMA


def build_agent_card(
    *,
    name: str,
    host: str,
    port: int,
    skills: list[dict | Skill],
    description: str | None = None,
    version: str = "1.0.0",
) -> AgentCard:
    skill_models = [s if isinstance(s, Skill) else Skill.model_validate(s) for s in skills]
    return AgentCard(
        name=name,
        description=description or f"A2A bridge adapter: {name}",
        url=f"http://{host}:{port}",
        version=version,
        protocols=["json-rpc-2.0"],
        capabilities=Capabilities(),
        authentication=Authentication(),
        skills=skill_models,
    )


def validate_against_schema(card: AgentCard | dict) -> None:
    payload = card.model_dump(mode="json") if isinstance(card, AgentCard) else card
    jsonschema.validate(instance=payload, schema=_load_schema())
