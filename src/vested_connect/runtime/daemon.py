"""One session: handshake + heartbeat + steady-state recv loop."""

from __future__ import annotations

import json as _json
import logging
import os
import socket
from typing import TYPE_CHECKING

from vested_connect.credential_handler import CredentialOpDispatcher
from vested_connect.errors import ConnectorError, TokenError
from vested_connect.proto import connector_hub_pb2 as pb

from ..tool_binding import resolve_bindings
from .fingerprint import compute_fingerprint
from .heartbeat import HeartbeatTimer
from .signals import SignalHandler

if TYPE_CHECKING:
    from vested_connect.app import ConnectorApp

    from .dispatcher import Dispatcher
    from .grpc_client import GrpcClient

logger = logging.getLogger("vested_connect.daemon")


# Reported in the Hello frame and stored as connectors.current_sdk_version,
# so the admin UI shows it. MUST track pyproject.toml — it had drifted to 0.2.0
# while the package was 0.4.0, making the operator view actively misleading.
SDK_VERSION = "0.5.2"


class Daemon:
    """One connector session. Returns an int exit code from run():
      0   — signal-driven graceful exit
      78  — token rejected / register rejected (EX_CONFIG)
      1   — any other transient error
    """

    def __init__(
        self,
        app: ConnectorApp,
        client: GrpcClient,
        *,
        signals: SignalHandler,
        dispatcher: Dispatcher | None = None,
        credential_ops: CredentialOpDispatcher | None = None,
        recv_timeout_s: float = 0.1,
    ) -> None:
        self.app = app
        self.client = client
        self.signals = signals
        # None when the connector declares no per-user credential handler.
        self._credential_ops = credential_ops
        self.handshake_completed = False
        self._heartbeat: HeartbeatTimer | None = None
        self._dispatcher = dispatcher
        # recv_timeout_s is a placeholder for future poll-tuning; stored but not yet used.
        self._recv_timeout_s = recv_timeout_s

    async def run(self) -> int:
        try:
            # 1. Hello
            hello = pb.ConnectorMsg()
            hello.hello.sdk_language = "python"
            hello.hello.sdk_version = SDK_VERSION
            hello.hello.worker_id = f"{socket.gethostname()}:{os.getpid()}"
            await self.client.send(hello)

            # 2. HelloAck
            ack_msg = await self.client.recv()
            if not ack_msg.HasField("hello_ack"):
                raise ConnectorError("expected HelloAck, got something else")
            logger.info(
                "connected to hub: connector_id=%s namespace=%s max_concurrent=%d",
                ack_msg.hello_ack.connector_id,
                ack_msg.hello_ack.namespace,
                ack_msg.hello_ack.max_concurrent_tool_calls,
            )

            # 3. Register
            register = self._build_register()
            await self.client.send(register)

            # 4. RegisterAck
            reg_ack_msg = await self.client.recv()
            if not reg_ack_msg.HasField("register_ack"):
                raise ConnectorError("expected RegisterAck")
            if reg_ack_msg.register_ack.status != "accepted":
                for issue in reg_ack_msg.register_ack.issues:
                    logger.error("register issue: %s", issue)
                raise TokenError("register rejected — see logs for issues")
            self.handshake_completed = True
            logger.info("registered with hub")

            # 5. Heartbeat
            self._heartbeat = HeartbeatTimer(self.client)
            self._heartbeat.start()

            # 6. Steady state
            return await self._steady_state()

        except TokenError as e:
            logger.error("token rejected: %s", e)
            return 78
        except ConnectorError as e:
            logger.warning("session ended: %s", e)
            return 1
        finally:
            if self._heartbeat is not None:
                await self._heartbeat.stop()

    async def _steady_state(self) -> int:
        while not self.signals.should_exit():
            try:
                msg = await self.client.recv()
            except ConnectorError as e:
                logger.info("stream closed: %s", e)
                return 1
            if msg.HasField("tool_call_request"):
                if self._dispatcher is None:
                    logger.warning(
                        "tool_call_request received but no dispatcher configured (tool=%s)",
                        msg.tool_call_request.tool_key,
                    )
                else:
                    self._dispatcher.dispatch(msg.tool_call_request)
            elif msg.HasField("credential_op_request"):
                # Answered inline: a credential op is one call to one system and
                # the platform is waiting on a bounded deadline. Silence would
                # make it wait the deadline out.
                if self._credential_ops is not None:
                    resp = self._credential_ops.dispatch(msg.credential_op_request)
                    await self.client.send(
                        pb.ConnectorMsg(credential_op_response=resp)
                    )
            elif msg.HasField("heartbeat_ack"):
                pass  # no-op
            elif msg.HasField("go_away"):
                reason = msg.go_away.reason
                logger.warning("GoAway from hub: %s", reason)
                if reason in ("revoked", "token_revoked"):
                    raise TokenError(f"hub revoked stream: {reason}")
                # Any other reason (e.g. "shutdown" during a hub deploy) is a
                # transient close. Return 1 so the supervisor reconnects after
                # backoff — keeps the worker warm across hub rollouts.
                return 1
        return 0

    def _build_register(self) -> pb.ConnectorMsg:
        msg = pb.ConnectorMsg()
        reg = msg.register
        # SHA256 over the canonical declaration shape. Non-empty fingerprint
        # is REQUIRED — the hub's in-memory store starts at "" so an empty
        # fingerprint trivially matches, the hub short-circuits "accepted"
        # without ever reconciling to Laravel, and agents/tools never land
        # in the DB. See runtime/fingerprint.py for the canonical shape.
        reg.baseline_fingerprint = compute_fingerprint(self.app.agents, self.app.tools)
        bound = resolve_bindings(self.app.agents, self.app.tools)
        for agent_decl in self.app.agents:
            a = reg.agents.add()
            a.key = agent_decl.key
            a.name = agent_decl.name
            a.description = agent_decl.description
            a.status = agent_decl.status
            provider, _, name = agent_decl.model.partition(":")
            a.model.provider = provider
            a.model.name = name
            for instr in agent_decl.instructions:
                idecl = a.instructions.add()
                idecl.type = instr.type
                idecl.format = instr.format
                idecl.body = instr.body
                idecl.position = instr.position
            # Tools bound to this agent — by namespace prefix, or by the
            # tool's own agents list. resolve_bindings is the single authority;
            # the fingerprint reads the same resolution, so the two cannot drift.
            for tool_decl in bound[agent_decl.key]:
                t = a.tools.add()
                t.key = tool_decl.key
                t.name = tool_decl.name
                t.description = tool_decl.description
                # input_schema_json / output_schema_json are bytes on the wire.
                t.input_schema_json = _json.dumps(tool_decl.input_schema).encode()
                t.output_schema_json = _json.dumps(tool_decl.output_schema).encode()
                t.default_deadline_ms = tool_decl.default_deadline_ms
                t.max_result_bytes = tool_decl.max_result_bytes
                t.sensitivity = tool_decl.sensitivity
        return msg
