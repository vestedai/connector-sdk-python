"""Periodic Heartbeat sender."""

from __future__ import annotations

import asyncio

from vested_connect.proto import connector_hub_pb2 as pb


class HeartbeatTimer:
    """Background asyncio.Task that sends Heartbeat to the hub every interval_s.

    Mirrors php-sdk HeartbeatTimer at 20s default (php-sdk uses 20_000 ms).
    """

    def __init__(self, client: object, interval_s: float = 20.0) -> None:
        # `client` is duck-typed: it must have `async send(ConnectorMsg)`.
        # Typed as object to avoid a circular import with GrpcClient.
        self.client = client
        self.interval_s = interval_s
        self._task: asyncio.Task[None] | None = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval_s)
            msg = pb.ConnectorMsg()
            msg.heartbeat.SetInParent()
            await self.client.send(msg)  # type: ignore[attr-defined]

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="heartbeat")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
