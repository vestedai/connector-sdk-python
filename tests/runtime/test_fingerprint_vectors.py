"""The baseline fingerprint is a CROSS-SDK contract.

dotnet, node and python canonicalise the same structure and the hub uses the
result to decide whether a connector changed. Nothing checked they agreed, and
two things did not: the sort comparer (locale vs culture vs ordinal) and
``model_config`` (dotnet emitted null where these two emit {}).

This fixture is the check. It is shared — ``vested-ai-sdks/testdata`` is
canonical and each SDK carries a generated copy, which
``scripts/verify-fingerprint-vectors.sh`` guards against drift.

php is deliberately NOT in this set: its canonical form nests tools inside
agent declarations and has never been comparable with these three.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from vested_connect.agent import AgentDeclaration, Instruction
from vested_connect.runtime.fingerprint import compute_fingerprint
from vested_connect.tool import ToolDeclaration

VECTORS_PATH = Path(__file__).parents[2] / "testdata" / "fingerprint-vectors.json"
VECTORS = json.loads(VECTORS_PATH.read_text())["vectors"]


def _agent(a: dict[str, Any]) -> AgentDeclaration:
    return AgentDeclaration(
        key=a["key"],
        name=a["name"],
        model=a["model"],
        description=a["description"],
        status=a["status"],
        instructions=[
            Instruction(
                type=i["type"],
                position=i["position"],
                body=i["body"],
                format=i["format"],
            )
            for i in a["instructions"]
        ],
        model_config=a["model_config"],
    )


def _tool(t: dict[str, Any]) -> ToolDeclaration:
    return ToolDeclaration(
        key=t["key"],
        name=t["name"],
        description=t["description"],
        sensitivity=t["sensitivity"],
        input_schema=t["input_schema"],
        output_schema=t["output_schema"],
        default_deadline_ms=t["default_deadline_ms"],
        max_result_bytes=t["max_result_bytes"],
        agents=tuple(t.get("agents", ())),
    )


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["name"])
def test_fingerprint_matches_cross_sdk_vector(vector: dict[str, Any]) -> None:
    agents = [_agent(a) for a in vector["agents"]]
    tools = {t["key"]: _tool(t) for t in vector["tools"]}

    assert compute_fingerprint(agents, tools) == vector["expected_sha256"], (
        f"vector {vector['name']!r} drifted — this SDK now disagrees with the "
        f"others about whether a connector changed"
    )
