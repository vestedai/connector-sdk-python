"""Dispatcher tests with a FakeClient — no real network."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from vested_connect import BaseModel, Field, ToolContext, ToolHandler, tool
from vested_connect.proto import connector_hub_pb2 as pb
from vested_connect.runtime.dispatcher import Dispatcher


@tool("test.echo", description="Echo input back.")
class Echo(ToolHandler):
    class Args(BaseModel):
        text: str = Field(description="Text to echo.")

    class Result(BaseModel):
        echoed: str

    async def handle(self, args: Echo.Args, ctx: ToolContext) -> Echo.Result:  # type: ignore[override]
        return Echo.Result(echoed=args.text + "!")


@tool("test.crashy", description="Always raises.")
class Crashy(ToolHandler):
    class Args(BaseModel):
        x: int

    async def handle(self, args: Crashy.Args, ctx: ToolContext) -> dict[str, Any]:  # type: ignore[override]
        raise RuntimeError("boom")


@tool("test.dict_result", description="Returns plain dict.")
class DictResult(ToolHandler):
    class Args(BaseModel):
        n: int

    async def handle(self, args: DictResult.Args, ctx: ToolContext) -> dict[str, Any]:  # type: ignore[override]
        return {"doubled": args.n * 2}


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[pb.ConnectorMsg] = []

    async def send(self, msg: pb.ConnectorMsg) -> None:
        self.sent.append(msg)


def _make_request(
    *, tool_key: str, args_json: str, invocation_id: str = "i1"
) -> pb.ToolCallRequest:
    req = pb.ToolCallRequest()
    req.invocation_id = invocation_id
    req.tool_key = tool_key
    # args_json is TYPE_BYTES on the wire.
    req.args_json = args_json.encode("utf-8")
    return req


@pytest.mark.asyncio
async def test_dispatch_success_pydantic_result() -> None:
    client = FakeClient()
    dispatcher = Dispatcher({Echo.__vested_tool__.key: Echo.__vested_tool__}, client)  # type: ignore[attr-defined]
    req = _make_request(tool_key="test.echo", args_json='{"text": "hi"}')

    await dispatcher._handle(req)
    assert len(client.sent) == 1
    resp = client.sent[0].tool_call_response
    assert resp.invocation_id == "i1"
    # result is set; error field is absent (default empty string).
    assert resp.error == ""

    # result_json is bytes on the wire; json.loads accepts bytes.
    assert json.loads(resp.result_json) == {"echoed": "hi!"}


@pytest.mark.asyncio
async def test_dispatch_success_dict_result() -> None:
    client = FakeClient()
    dispatcher = Dispatcher({DictResult.__vested_tool__.key: DictResult.__vested_tool__}, client)  # type: ignore[attr-defined]
    req = _make_request(tool_key="test.dict_result", args_json='{"n": 7}')

    await dispatcher._handle(req)
    assert len(client.sent) == 1
    assert json.loads(client.sent[0].tool_call_response.result_json) == {"doubled": 14}


@pytest.mark.asyncio
async def test_dispatch_unknown_tool() -> None:
    client = FakeClient()
    dispatcher = Dispatcher({}, client)
    req = _make_request(tool_key="does.not.exist", args_json="{}")
    await dispatcher._handle(req)
    # ToolCallResponse.error is the wire field name (not error_message).
    assert "unknown tool" in client.sent[0].tool_call_response.error


@pytest.mark.asyncio
async def test_dispatch_invalid_args() -> None:
    client = FakeClient()
    dispatcher = Dispatcher({Echo.__vested_tool__.key: Echo.__vested_tool__}, client)  # type: ignore[attr-defined]
    req = _make_request(tool_key="test.echo", args_json='{"text": 123}')  # int not str
    await dispatcher._handle(req)
    assert "tool_call_invalid_args" in client.sent[0].tool_call_response.error


@pytest.mark.asyncio
async def test_dispatch_handler_crash_becomes_error_reply() -> None:
    client = FakeClient()
    dispatcher = Dispatcher({Crashy.__vested_tool__.key: Crashy.__vested_tool__}, client)  # type: ignore[attr-defined]
    req = _make_request(tool_key="test.crashy", args_json='{"x": 1}')
    await dispatcher._handle(req)
    assert "boom" in client.sent[0].tool_call_response.error


@pytest.mark.asyncio
async def test_dispatch_uses_invocation_id_on_response() -> None:
    client = FakeClient()
    dispatcher = Dispatcher({Echo.__vested_tool__.key: Echo.__vested_tool__}, client)  # type: ignore[attr-defined]
    req = _make_request(
        tool_key="test.echo", args_json='{"text": "x"}', invocation_id="custom-id-42"
    )
    await dispatcher._handle(req)
    assert client.sent[0].tool_call_response.invocation_id == "custom-id-42"


@pytest.mark.asyncio
async def test_dispatch_ctx_erp_fields_populated() -> None:
    """ERP identity fields on ToolCallRequest surface on the ToolContext."""
    captured_ctx: list[ToolContext] = []

    @tool("test.ctx_capture_erp", description="Capture ctx for assertion.")
    class CtxCaptureErp(ToolHandler):
        class Args(BaseModel):
            pass

        async def handle(self, args: Args, ctx: ToolContext) -> dict[str, object]:  # type: ignore[override]
            captured_ctx.append(ctx)
            return {}

    client = FakeClient()
    dispatcher = Dispatcher(
        {CtxCaptureErp.__vested_tool__.key: CtxCaptureErp.__vested_tool__},  # type: ignore[attr-defined]
        client,
    )
    req = pb.ToolCallRequest()
    req.invocation_id = "erp-test-1"
    req.tool_key = "test.ctx_capture_erp"
    req.args_json = b"{}"
    req.employee_no = "EMP-001"
    req.erp_identifier = "SAP-98765"
    req.erp_department_identifiers.extend(["DEPT-A", "DEPT-B"])

    await dispatcher._handle(req)

    assert len(captured_ctx) == 1
    ctx = captured_ctx[0]
    assert ctx.employee_no == "EMP-001"
    assert ctx.erp_identifier == "SAP-98765"
    assert ctx.erp_department_identifiers == ("DEPT-A", "DEPT-B")


@pytest.mark.asyncio
async def test_dispatch_ctx_erp_fields_default_when_absent() -> None:
    """ERP identity fields default to empty string / empty tuple when absent."""
    captured_ctx: list[ToolContext] = []

    @tool("test.ctx_capture_erp_default", description="Capture ctx defaults.")
    class CtxCaptureErpDefault(ToolHandler):
        class Args(BaseModel):
            pass

        async def handle(self, args: Args, ctx: ToolContext) -> dict[str, object]:  # type: ignore[override]
            captured_ctx.append(ctx)
            return {}

    client = FakeClient()
    dispatcher = Dispatcher(
        {CtxCaptureErpDefault.__vested_tool__.key: CtxCaptureErpDefault.__vested_tool__},  # type: ignore[attr-defined]
        client,
    )
    req = pb.ToolCallRequest()
    req.invocation_id = "erp-default-1"
    req.tool_key = "test.ctx_capture_erp_default"
    req.args_json = b"{}"
    # erp fields intentionally not set

    await dispatcher._handle(req)

    assert len(captured_ctx) == 1
    ctx = captured_ctx[0]
    assert ctx.employee_no == ""
    assert ctx.erp_identifier == ""
    assert ctx.erp_department_identifiers == ()


@pytest.mark.asyncio
async def test_dispatch_spawns_task_for_concurrency() -> None:
    """dispatch() (not _handle) should return immediately, leaving the
    actual work for the spawned Task."""
    client = FakeClient()
    dispatcher = Dispatcher({Echo.__vested_tool__.key: Echo.__vested_tool__}, client)  # type: ignore[attr-defined]
    req = _make_request(tool_key="test.echo", args_json='{"text": "ok"}')

    dispatcher.dispatch(req)
    # Right after dispatch, nothing should be sent yet (Task hasn't run).
    assert client.sent == []
    # Yield to let the Task run.
    await asyncio.sleep(0.05)
    assert len(client.sent) == 1
