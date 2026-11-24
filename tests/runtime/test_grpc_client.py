"""Unit tests for GrpcClient channel liveness options.

The 2026-11-24 incident (PHP/Swoole SDK: a dead hub stream spun 100% CPU
for six days, no logs, no reconnect) exposed the whole failure class: a
connector whose hub stream dies silently — graceful FIN, half-open socket
after a relay restart, WireGuard rekey, network partition — and nothing
detects it. gRPC core transports all ship with keepalive PINGs suppressed
while no unary call is pending, and the Connect bidi stream carries none
in steady state, so the channel options ARE the detection layer: on a
dead socket the PING times out, the stream errors, the supervisor redials.
These tests pin the options the channel must be created with.
"""

from __future__ import annotations

from typing import Any

import pytest
from grpc import aio as grpc_aio

from vested_connect.runtime.grpc_client import GrpcClient

KEEPALIVE_TIME_MS = 30_000
KEEPALIVE_TIMEOUT_MS = 10_000


class _FakeCall:
    def cancel(self) -> None:
        pass


class _FakeChannel:
    """Just enough of grpc.aio.Channel for the client lifecycle.

    ``stream_stream`` is bound eagerly when the stub is constructed, so it
    must exist and return a callable that yields a cancelable call.
    """

    def __init__(self) -> None:
        self.closed = False

    def stream_stream(self, *args: Any, **kwargs: Any) -> Any:
        def _bind(request_iterator: Any, metadata: Any = None) -> _FakeCall:
            return _FakeCall()

        return _bind

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def capture_channels(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the channel factories; record the options each receives.

    Patched on the ``grpc.aio`` module itself: the client's
    ``from grpc import aio`` binds the same module object, so the
    attribute swap is visible through its namespace too.
    """
    captured: dict[str, Any] = {}

    def _fake_insecure(target: str, options: Any = None, **kw: Any) -> _FakeChannel:
        captured["insecure"] = options
        return _FakeChannel()

    def _fake_secure(
        target: str, credentials: Any = None, options: Any = None, **kw: Any
    ) -> _FakeChannel:
        captured["secure"] = options
        return _FakeChannel()

    monkeypatch.setattr(grpc_aio, "insecure_channel", _fake_insecure)
    monkeypatch.setattr(grpc_aio, "secure_channel", _fake_secure)
    return captured


def _expect_keepalive(options: Any) -> None:
    assert options is not None, "channel created without keepalive options"
    opts = dict(options)
    assert opts.get("grpc.keepalive_time_ms") == KEEPALIVE_TIME_MS
    assert opts.get("grpc.keepalive_timeout_ms") == KEEPALIVE_TIMEOUT_MS
    assert opts.get("grpc.keepalive_permit_without_calls") == 1


async def test_insecure_channel_is_created_with_keepalive_options(
    capture_channels: dict[str, Any],
) -> None:
    client = GrpcClient("hub.example", 4443, "token", insecure=True)
    await client.__aenter__()
    await client.__aexit__()
    _expect_keepalive(capture_channels["insecure"])


async def test_secure_channel_is_created_with_keepalive_options(
    capture_channels: dict[str, Any],
) -> None:
    client = GrpcClient("hub.example", 4443, "token", insecure=False)
    await client.__aenter__()
    await client.__aexit__()
    _expect_keepalive(capture_channels["secure"])
