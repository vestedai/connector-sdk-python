"""Integration tests: full daemon session against the in-process fake hub.

Covers:
  - Happy path: Hello → HelloAck → Register → RegisterAck(accepted) →
    ToolCallRequest → ToolCallResponse → GoAway("shutdown") → exit 0.
  - Register rejected → exit 78.
  - GoAway("revoked") mid-stream → exit 78 (daemon raises TokenError).
"""

from __future__ import annotations

import json

import pytest

from tests.fixtures.fake_hub import FakeHubScript, ToolInvocation, fake_hub
from vested_connect import BaseModel, ConnectorApp, Field, ToolHandler, agent, tool
from vested_connect.runtime.supervisor import run_supervised

# ---------------------------------------------------------------------------
# Minimal app: one agent + one echo tool
# ---------------------------------------------------------------------------


@agent(key="t.test", name="Test", model="openai:gpt-4o")
class _Agent:
    pass


@tool("t.test.echo", description="echo")
class _Echo(ToolHandler):
    class Args(BaseModel):
        text: str = Field(description="echo me")

    class Result(BaseModel):
        echoed: str

    async def handle(self, args: Args, ctx: object) -> Result:  # type: ignore[override]
        return _Echo.Result(echoed=args.text)


def _build_app() -> ConnectorApp:
    """Build a ConnectorApp directly without scan_module."""
    app = ConnectorApp.create()
    app._agents.append(_Agent.__vested_agent__)  # type: ignore[attr-defined]
    app._tools["t.test.echo"] = _Echo.__vested_tool__  # type: ignore[attr-defined]
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_session_roundtrip() -> None:
    """Daemon connects, registers, handles a tool call, exits cleanly on GoAway."""
    script = FakeHubScript(
        accept_register=True,
        tool_calls=[
            ToolInvocation(
                tool_key="t.test.echo",
                args_json=json.dumps({"text": "hi"}).encode(),
                expected_invocation_id="inv-1",
            )
        ],
        final_goaway_reason="shutdown",
    )
    async with fake_hub(script) as (hub, port):
        exit_code = await run_supervised(
            _build_app(),
            token="t.test.token",
            host="127.0.0.1",
            port=port,
            insecure=True,
        )

    assert exit_code == 0, f"expected exit 0, got {exit_code}"
    assert hub.received_hello is not None, "hub never received Hello"
    assert hub.received_register is not None, "hub never received Register"
    assert len(hub.received_tool_responses) == 1, (
        f"expected 1 tool response, got {len(hub.received_tool_responses)}"
    )

    resp = hub.received_tool_responses[0]
    assert resp.invocation_id == "inv-1"
    # ToolCallResponse uses a oneof 'result' field — ok means result_json is set.
    assert resp.WhichOneof("result") == "result_json", (
        f"expected result_json, got error: {resp.error!r}"
    )
    body = json.loads(resp.result_json.decode())
    assert body == {"echoed": "hi"}, f"unexpected result body: {body}"


@pytest.mark.asyncio
async def test_register_rejected_exits_78() -> None:
    """Hub rejects Register → supervisor returns 78 (token/config error)."""
    script = FakeHubScript(
        accept_register=False,
        register_reject_reason="token revoked",
    )
    async with fake_hub(script) as (_hub, port):
        exit_code = await run_supervised(
            _build_app(),
            token="t.test.token",
            host="127.0.0.1",
            port=port,
            insecure=True,
        )

    assert exit_code == 78, f"expected exit 78, got {exit_code}"


@pytest.mark.asyncio
async def test_goaway_revoked_exits_78() -> None:
    """GoAway(reason='revoked') mid-stream is treated as terminal — exit 78.

    The daemon's _steady_state handler raises TokenError for reason in
    ('revoked', 'token_revoked'), which propagates through supervisor as 78.
    """
    script = FakeHubScript(
        accept_register=True,
        tool_calls=[],
        final_goaway_reason="revoked",
    )
    async with fake_hub(script) as (_hub, port):
        exit_code = await run_supervised(
            _build_app(),
            token="t.test.token",
            host="127.0.0.1",
            port=port,
            insecure=True,
        )

    assert exit_code == 78, f"expected exit 78, got {exit_code}"
