"""Tests for runtime.fingerprint."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vested_connect import Instruction, ToolHandler, agent, tool
from vested_connect.runtime.fingerprint import compute_fingerprint


@agent(
    key="t.alpha",
    name="Alpha",
    model="openai:gpt-4o",
    instructions=[Instruction(type="system", position=0, body="hello")],
)
class _Alpha: ...


@tool("t.alpha.echo", description="echo")
class _Echo(ToolHandler):
    class Args(BaseModel):
        text: str = Field(description="echo me")

    async def handle(self, args, ctx):  # type: ignore[no-untyped-def]
        return {}


def _agents() -> list[object]:
    return [_Alpha.__vested_agent__]  # type: ignore[attr-defined]


def _tools() -> dict[str, object]:
    return {"t.alpha.echo": _Echo.__vested_tool__}  # type: ignore[attr-defined]


def test_fingerprint_is_non_empty() -> None:
    """An empty fingerprint trivially matches the hub's initial store —
    that would short-circuit the Laravel reconcile and the connector
    would never actually register its declarations."""
    fp = compute_fingerprint(_agents(), _tools())  # type: ignore[arg-type]
    assert fp != ""
    assert len(fp) == 64  # sha256 hex


def test_fingerprint_is_stable() -> None:
    """Same declarations → same hash. Required for reconnect to short-circuit."""
    a = compute_fingerprint(_agents(), _tools())  # type: ignore[arg-type]
    b = compute_fingerprint(_agents(), _tools())  # type: ignore[arg-type]
    assert a == b


def test_fingerprint_differs_when_declarations_differ() -> None:
    """Different declarations → different hash. Required for the hub to
    fall through to Laravel reconcile after a baseline change."""
    baseline = compute_fingerprint(_agents(), _tools())  # type: ignore[arg-type]
    no_tools = compute_fingerprint(_agents(), {})  # type: ignore[arg-type]
    assert baseline != no_tools
    no_agents = compute_fingerprint([], _tools())  # type: ignore[arg-type]
    assert baseline != no_agents
