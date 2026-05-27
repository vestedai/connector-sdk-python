"""Bidi gRPC client for the connector hub."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import cast

import grpc
from grpc import aio

from vested_connect.errors import ConnectorError, TokenError
from vested_connect.proto import connector_hub_pb2 as pb
from vested_connect.proto import connector_hub_pb2_grpc as pb_grpc


class GrpcClient:
    """Bidi stream to ConnectorHub.Connect.

    Usage::

        async with GrpcClient(host, port, token, insecure=False) as client:
            await client.send(connector_msg)
            hub_msg = await client.recv()
    """

    def __init__(self, host: str, port: int, token: str, insecure: bool = False) -> None:
        self.host = host
        self.port = port
        self.token = token
        self.insecure = insecure
        self._channel: aio.Channel | None = None
        self._outbound_q: asyncio.Queue[pb.ConnectorMsg] = asyncio.Queue()
        self._stream: aio.StreamStreamCall[pb.ConnectorMsg, pb.HubMsg] | None = None

    async def __aenter__(self) -> GrpcClient:
        target = f"{self.host}:{self.port}"
        if self.insecure:
            self._channel = aio.insecure_channel(target)
        else:
            self._channel = aio.secure_channel(target, grpc.ssl_channel_credentials())
        stub = pb_grpc.ConnectorHubStub(self._channel)  # type: ignore[no-untyped-call]
        metadata = (("x-connector-token", self.token),)
        self._stream = stub.Connect(self._outbound_gen(), metadata=metadata)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._stream is not None:
            self._stream.cancel()
        if self._channel is not None:
            await self._channel.close()

    async def _outbound_gen(self) -> AsyncIterator[pb.ConnectorMsg]:
        while True:
            msg = await self._outbound_q.get()
            yield msg

    async def send(self, msg: pb.ConnectorMsg) -> None:
        await self._outbound_q.put(msg)

    async def recv(self) -> pb.HubMsg:
        if self._stream is None:
            raise ConnectorError("stream not opened")
        try:
            raw = await self._stream.read()
        except aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.UNAUTHENTICATED:
                raise TokenError(e.details() or "unauthenticated") from e
            raise ConnectorError(f"stream error: {e.details()}") from e
        # grpcio-async returns EOF marker (some versions: grpc.aio.EOF; others: a sentinel)
        # Check for None first (more common in newer grpcio).
        if raw is None:
            raise ConnectorError("stream closed by hub")
        return cast(pb.HubMsg, raw)
