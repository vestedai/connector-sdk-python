"""Route ToolCallRequest → handler → ToolCallResponse."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol

from vested_connect.errors import ToolValidationError
from vested_connect.proto import connector_hub_pb2 as pb
from vested_connect.tool import ToolContext, ToolDeclaration, validate_args

logger = logging.getLogger("vested_connect.dispatcher")


class _Sender(Protocol):
    """Structural type for anything that can send a ConnectorMsg."""

    async def send(self, msg: pb.ConnectorMsg) -> None: ...


class Dispatcher:
    """Routes ToolCallRequest frames to registered ToolHandlers.

    Each dispatch spawns an asyncio.Task so the daemon's main recv loop
    keeps reading concurrent calls. Handler results / errors round-trip
    back as ToolCallResponse frames via the client's outbound queue.
    """

    def __init__(
        self,
        registry: dict[str, ToolDeclaration],
        client: _Sender,
    ) -> None:
        self.registry = registry
        self.client = client

    def dispatch(self, req: pb.ToolCallRequest) -> None:
        """Fire-and-forget: spawn a Task; don't block the recv loop."""
        asyncio.create_task(
            self._handle(req),
            name=f"tool/{req.tool_key}/{req.invocation_id}",
        )

    async def _handle(self, req: pb.ToolCallRequest) -> None:
        decl = self.registry.get(req.tool_key)
        if decl is None:
            await self._reply_error(req, f"unknown tool: {req.tool_key}")
            return

        raw_args = self._get_args_json(req)

        try:
            args = validate_args(decl, raw_args)
        except ToolValidationError as e:
            await self._reply_error(req, f"tool_call_invalid_args: {e}")
            return

        ctx = self._build_ctx(req)

        assert decl.handler_cls is not None
        handler = decl.handler_cls()
        try:
            result = await handler.handle(args, ctx)
        except Exception as e:  # noqa: BLE001 — handler errors must not crash daemon
            logger.exception("tool handler crashed: %s", req.tool_key)
            await self._reply_error(req, str(e))
            return

        result_json = self._serialise_result(result)
        if result_json is None:
            await self._reply_error(req, "handler must return Pydantic model or dict")
            return
        await self._reply_ok(req, result_json)

    @staticmethod
    def _get_args_json(req: pb.ToolCallRequest) -> str:
        """Extract args JSON. Tolerate str/bytes wire shape."""
        raw = getattr(req, "args_json", "")
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)

    @staticmethod
    def _build_ctx(req: pb.ToolCallRequest) -> ToolContext:
        """Build ToolContext from request fields. Tolerate missing fields."""
        return ToolContext(
            org_id=int(getattr(req, "organization_id", 0) or 0),
            agent_key=str(getattr(req, "agent_key", "")),
            run_id=str(getattr(req, "run_id", "")),
            conversation_id=str(getattr(req, "conversation_id", "")),
            user_email=str(getattr(req, "user_email", "")),
            user_id=int(getattr(req, "user_id", 0) or 0),
            employee_no=str(getattr(req, "employee_no", "")),
            erp_identifier=str(getattr(req, "erp_identifier", "")),
            erp_department_identifiers=tuple(getattr(req, "erp_department_identifiers", ())),
        )

    @staticmethod
    def _serialise_result(result: Any) -> str | None:
        if hasattr(result, "model_dump_json"):
            return str(result.model_dump_json())
        if isinstance(result, dict):
            return json.dumps(result)
        return None

    async def _reply_ok(self, req: pb.ToolCallRequest, result_json: str) -> None:
        msg = pb.ConnectorMsg()
        resp = msg.tool_call_response
        resp.invocation_id = req.invocation_id
        # result_json is TYPE_BYTES on the wire; encode from str.
        resp.result_json = result_json.encode("utf-8")
        await self.client.send(msg)

    async def _reply_error(self, req: pb.ToolCallRequest, error: str) -> None:
        msg = pb.ConnectorMsg()
        resp = msg.tool_call_response
        resp.invocation_id = req.invocation_id
        resp.error = error
        await self.client.send(msg)
