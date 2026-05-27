"""Scriptable in-process gRPC fake hub for integration tests.

The ConnectorHub protocol is asymmetric:
  - client → hub: ConnectorMsg  (Hello, Register, ToolCallResponse, Heartbeat)
  - hub → client: HubMsg        (HelloAck, RegisterAck, ToolCallRequest, GoAway, HeartbeatAck)

Usage::

    script = FakeHubScript(
        accept_register=True,
        tool_calls=[ToolInvocation("my.tool", b'{"x": 1}', "inv-1")],
        final_goaway_reason="shutdown",
    )
    async with fake_hub(script) as (servicer, port):
        exit_code = await run_supervised(
            app, token="tok", host="127.0.0.1", port=port, insecure=True
        )
    assert servicer.received_hello is not None
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import grpc

from vested_connect.proto import connector_hub_pb2 as pb
from vested_connect.proto import connector_hub_pb2_grpc as pb_grpc

logger = logging.getLogger("tests.fake_hub")


@dataclass
class ToolInvocation:
    """One scripted tool call the hub issues to the daemon."""

    tool_key: str
    args_json: bytes
    expected_invocation_id: str = "inv-1"


@dataclass
class FakeHubScript:
    """Declarative script describing what the fake hub does in a session.

    Steps:
      1. Hub awaits Hello → sends HelloAck.
      2. Hub awaits Register → sends RegisterAck(status="accepted" or "rejected").
      3. If accepted: for each tool_call → sends ToolCallRequest, awaits ToolCallResponse.
      4. After all tool calls (or immediately on reject): sends GoAway(reason) if non-empty.
    """

    accept_register: bool = True
    register_reject_reason: str = ""
    tool_calls: list[ToolInvocation] = field(default_factory=list)
    # Set to "" to skip GoAway (daemon must be stopped externally).
    final_goaway_reason: str = "shutdown"


class FakeHub(pb_grpc.ConnectorHubServicer):
    """Stateful servicer that runs one scripted session."""

    def __init__(self, script: FakeHubScript) -> None:
        self.script = script
        # Observations the test can assert on:
        self.received_hello: pb.Hello | None = None
        self.received_register: pb.Register | None = None
        self.received_tool_responses: list[pb.ToolCallResponse] = []
        self.handshake_complete: asyncio.Event = asyncio.Event()
        self.all_tool_calls_done: asyncio.Event = asyncio.Event()

    async def Connect(
        self,
        request_iterator: AsyncIterator[pb.ConnectorMsg],
        context: grpc.aio.ServicerContext,  # type: ignore[type-arg]
    ) -> AsyncIterator[pb.HubMsg]:
        # Step 1: await Hello
        async for msg in request_iterator:
            which = msg.WhichOneof("body")
            if which == "hello":
                self.received_hello = msg.hello
                logger.debug(
                    "fake_hub: got Hello sdk_version=%s", msg.hello.sdk_version
                )
                yield pb.HubMsg(
                    hello_ack=pb.HelloAck(
                        connector_id="test-connector",
                        namespace="test",
                    )
                )
                break
            else:
                logger.warning("fake_hub: unexpected message before Hello: %s", which)

        # Step 2: await Register
        async for msg in request_iterator:
            which = msg.WhichOneof("body")
            if which == "heartbeat":
                # Daemon may send a heartbeat before Register — ignore.
                continue
            if which == "register":
                self.received_register = msg.register
                logger.debug("fake_hub: got Register")
                if self.script.accept_register:
                    yield pb.HubMsg(
                        register_ack=pb.RegisterAck(
                            status="accepted",
                            baseline_fingerprint="",
                        )
                    )
                    self.handshake_complete.set()
                else:
                    reason = self.script.register_reject_reason or "rejected by script"
                    yield pb.HubMsg(
                        register_ack=pb.RegisterAck(
                            status="rejected",
                            issues=[pb.DeclIssue(code="TOKEN_ERROR", message=reason)],
                        )
                    )
                    # No GoAway needed; daemon exits on its own.
                    return
                break
            else:
                logger.warning(
                    "fake_hub: unexpected message before Register: %s", which
                )

        if not self.script.accept_register:
            return

        # Step 3: issue scripted tool calls
        for invocation in self.script.tool_calls:
            logger.debug(
                "fake_hub: issuing ToolCallRequest tool_key=%s", invocation.tool_key
            )
            yield pb.HubMsg(
                tool_call_request=pb.ToolCallRequest(
                    invocation_id=invocation.expected_invocation_id,
                    tool_key=invocation.tool_key,
                    args_json=invocation.args_json,
                )
            )

            # Await the matching ToolCallResponse (skip heartbeats in between).
            response_received = False
            async for msg in request_iterator:
                which = msg.WhichOneof("body")
                if which == "heartbeat":
                    # Absorb heartbeats; send HeartbeatAck so the client doesn't stall.
                    yield pb.HubMsg(heartbeat_ack=pb.HeartbeatAck())
                    continue
                if which == "tool_call_response":
                    resp = msg.tool_call_response
                    logger.debug(
                        "fake_hub: got ToolCallResponse invocation_id=%s ok=%s",
                        resp.invocation_id,
                        resp.WhichOneof("result") == "result_json",
                    )
                    self.received_tool_responses.append(resp)
                    response_received = True
                    break
                else:
                    logger.warning(
                        "fake_hub: unexpected message while waiting for ToolCallResponse: %s",
                        which,
                    )
            if not response_received:
                logger.warning(
                    "fake_hub: stream ended before ToolCallResponse for %s",
                    invocation.expected_invocation_id,
                )
                return

        self.all_tool_calls_done.set()

        # Step 4: send GoAway
        if self.script.final_goaway_reason:
            logger.debug(
                "fake_hub: sending GoAway reason=%s", self.script.final_goaway_reason
            )
            yield pb.HubMsg(go_away=pb.GoAway(reason=self.script.final_goaway_reason))


@asynccontextmanager
async def fake_hub(script: FakeHubScript) -> AsyncIterator[tuple[FakeHub, int]]:
    """Start an in-process gRPC server on a random port.

    Yields (servicer, port). The server is stopped on exit.
    """
    servicer = FakeHub(script)
    server = grpc.aio.server()
    pb_grpc.add_ConnectorHubServicer_to_server(servicer, server)  # type: ignore[no-untyped-call]
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        yield servicer, port
    finally:
        await server.stop(grace=0.5)
