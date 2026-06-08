"""Deterministic fingerprint over the connector's agent + tool declarations.

The hub uses this to short-circuit re-registration: if a connector reconnects
with the same fingerprint it had last time, the hub skips the round-trip to
Laravel and replies "accepted" immediately. An EMPTY fingerprint trivially
matches the empty initial value in the hub's store, so a connector that sends
"" is never actually reconciled and its declarations never land in the DB.

We hash the canonical declaration shape — sorted lists, sorted JSON keys —
so the same SDK app produces the same hash across restarts.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vested_connect.agent import AgentDeclaration
    from vested_connect.tool import ToolDeclaration


def compute_fingerprint(
    agents: list[AgentDeclaration],
    tools: dict[str, ToolDeclaration],
) -> str:
    """SHA256 hex over the canonical declaration shape."""
    canonical: dict[str, object] = {
        "agents": [
            {
                "key": a.key,
                "name": a.name or a.key,
                "description": a.description,
                "status": a.status,
                "model": a.model,
                "model_config": a.model_config,
                "instructions": [
                    {
                        "type": i.type,
                        "position": i.position,
                        "body": i.body,
                        "format": i.format,
                    }
                    for i in sorted(a.instructions, key=lambda x: x.position)
                ],
            }
            for a in sorted(agents, key=lambda x: x.key)
        ],
        "tools": [
            {
                "key": t.key,
                "name": t.name,
                "description": t.description,
                "sensitivity": t.sensitivity,
                "input_schema": t.input_schema,
                "output_schema": t.output_schema,
                "default_deadline_ms": t.default_deadline_ms,
                "max_result_bytes": t.max_result_bytes,
            }
            for _, t in sorted(tools.items())
        ],
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
