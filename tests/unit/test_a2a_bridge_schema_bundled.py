"""Guard: the agent-card schema bundled into the a2a-bridge package matches the spec.

The a2a-bridge service loads `agent-card.schema.json` from a copy packaged next to
`a2a_bridge.protocol` so it resolves when installed as a wheel / uv tool (the repo's
`specs/` tree is absent there). This test keeps that copy in lockstep with the
in-repo source of truth under `specs/001-a2a-bridge/contracts/`.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = REPO_ROOT / "specs" / "001-a2a-bridge" / "contracts" / "agent-card.schema.json"
_PACKAGED = (
    REPO_ROOT
    / "services"
    / "a2a-bridge"
    / "src"
    / "a2a_bridge"
    / "protocol"
    / "agent-card.schema.json"
)


def test_packaged_agent_card_schema_matches_spec():
    assert _PACKAGED.is_file()

    spec = json.loads(_SPEC.read_text(encoding="utf-8"))
    packaged = json.loads(_PACKAGED.read_text(encoding="utf-8"))

    assert packaged == spec
