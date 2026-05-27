"""Unit tests for Daemon — handshake state and error paths.

These tests stub the GrpcClient so no real network connection is made.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import pytest

from vested_connect.errors import TokenError
from vested_connect.proto import connector_hub_pb2 as pb
from vested_connect.runtime.daemon import Daemon
from vested_connect.runtime.signals import SignalHandler

# ---------------------------------------------------------------------------
# Minimal stub helpers
# ---------------------------------------------------------------------------


class _StubApp:
    """Minimal app stub — no agents, no tools."""

    @property
    def agents(self) -> list[object]:
        return []

    @property
    def tools(self) -> dict[str, object]:
        return {}


class _StubClient:
    """Controllable fake GrpcClient.

    Preload recv_queue with HubMsg instances to be returned in order.
    Captures sent ConnectorMsg objects in sent_msgs.
    Raises the exception in send_error (if set) on the next send().
    """

    def __init__(
        self,
        recv_queue: list[pb.HubMsg] | None = None,
        recv_error: Exception | None = None,
    ) -> None:
        self._recv_queue: deque[pb.HubMsg | Exception] = deque(recv_queue or [])
        if recv_error is not None:
            self._recv_queue.append(recv_error)
        self.sent_msgs: list[pb.ConnectorMsg] = []

    async def send(self, msg: pb.ConnectorMsg) -> None:
        self.sent_msgs.append(msg)

    async def recv(self) -> pb.HubMsg:
        if not self._recv_queue:
            raise RuntimeError("stub recv queue exhausted")
        item = self._recv_queue.popleft()
        if isinstance(item, Exception):
            raise item
        return item


class _ImmediateExitSignals:
    """Signals that reports should_exit() == True from the first poll."""

    def should_exit(self) -> bool:
        return True

    async def wait(self) -> None:
        pass


class _NeverExitSignals:
    """Signals that never set exit — use with queues that exhaust naturally."""

    def should_exit(self) -> bool:
        return False

    async def wait(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handshake_completed_false_before_register_ack() -> None:
    """Daemon.handshake_completed is False until RegisterAck(accepted) arrives."""
    # Provide a HelloAck then a RegisterAck with status NOT "accepted",
    # so the daemon raises TokenError and exits 78 — but we can inspect
    # handshake_completed after run().
    hello_ack = pb.HubMsg(
        hello_ack=pb.HelloAck(
            connector_id="c1",
            namespace="ns",
        )
    )
    register_ack_rejected = pb.HubMsg(
        register_ack=pb.RegisterAck(
            status="rejected",
            issues=[pb.DeclIssue(code="E", message="bad token")],
        )
    )
    client = _StubClient(recv_queue=[hello_ack, register_ack_rejected])
    signals = SignalHandler()
    daemon = Daemon(_StubApp(), client, signals=signals)  # type: ignore[arg-type]

    assert daemon.handshake_completed is False, "should start False"
    code = await daemon.run()
    assert code == 78
    assert daemon.handshake_completed is False, "should remain False after rejection"


@pytest.mark.asyncio
async def test_handshake_completed_true_after_register_ack_accepted() -> None:
    """Daemon.handshake_completed is True once RegisterAck(accepted) arrives."""
    hello_ack = pb.HubMsg(
        hello_ack=pb.HelloAck(
            connector_id="c1",
            namespace="ns",
        )
    )
    register_ack_ok = pb.HubMsg(
        register_ack=pb.RegisterAck(status="accepted")
    )
    go_away = pb.HubMsg(go_away=pb.GoAway(reason="shutdown"))

    client = _StubClient(recv_queue=[hello_ack, register_ack_ok, go_away])
    signals = SignalHandler()
    daemon = Daemon(_StubApp(), client, signals=signals)  # type: ignore[arg-type]

    code = await daemon.run()
    assert code in (0, 1), f"unexpected exit code: {code}"
    assert daemon.handshake_completed is True, (
        "handshake_completed should be True after RegisterAck(accepted)"
    )


@pytest.mark.asyncio
async def test_daemon_returns_78_when_client_raises_token_error() -> None:
    """If recv() raises TokenError (e.g. UNAUTHENTICATED), Daemon exits 78."""

    class _TokenErrorClient:
        sent_msgs: list[Any] = []

        async def send(self, msg: pb.ConnectorMsg) -> None:
            _TokenErrorClient.sent_msgs.append(msg)

        async def recv(self) -> pb.HubMsg:
            raise TokenError("UNAUTHENTICATED: bad token")

    client = _TokenErrorClient()
    signals = SignalHandler()
    daemon = Daemon(_StubApp(), client, signals=signals)  # type: ignore[arg-type]

    code = await daemon.run()
    assert code == 78, f"expected 78 for TokenError, got {code}"


@pytest.mark.asyncio
async def test_daemon_returns_1_on_connector_error_at_hello_ack() -> None:
    """A non-HelloAck response to Hello produces exit code 1 (transient error)."""
    # Send a GoAway when the daemon expects a HelloAck.
    unexpected = pb.HubMsg(go_away=pb.GoAway(reason="shutdown"))
    client = _StubClient(recv_queue=[unexpected])
    signals = SignalHandler()
    daemon = Daemon(_StubApp(), client, signals=signals)  # type: ignore[arg-type]

    code = await daemon.run()
    assert code == 1, f"expected 1 for unexpected HelloAck, got {code}"
