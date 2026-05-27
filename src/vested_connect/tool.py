"""@tool decorator + ToolHandler base + ToolContext + validate_args helper."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from .errors import ToolValidationError


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Per-invocation context the hub provides on each ToolCallRequest.

    Tools use this for tenant scoping, audit fields, and to correlate
    against the run/conversation graph.
    """

    org_id: int
    agent_key: str
    run_id: str
    conversation_id: str
    user_email: str = ""
    user_id: int = 0


@dataclass
class ToolDeclaration:
    """What the @tool decorator stamps onto a class."""

    key: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    default_deadline_ms: int = 30_000
    max_result_bytes: int = 1_048_576
    handler_cls: type[ToolHandler] | None = None


class ToolHandler:
    """Base class for tool handlers.

    Subclasses MUST define an inner ``Args(BaseModel)`` and SHOULD define
    an inner ``Result(BaseModel)``. The handler method receives a validated
    Args instance and returns either a Result instance or a plain dict
    that must serialise to JSON.

    Example::

        @tool("acme.echo", description="Echo the input back.")
        class Echo(ToolHandler):
            class Args(BaseModel):
                text: str

            class Result(BaseModel):
                echoed: str

            async def handle(self, args: Args, ctx: ToolContext) -> Result:
                return Echo.Result(echoed=args.text)
    """

    Args: type[BaseModel]
    Result: type[BaseModel] | None = None

    async def handle(
        self,
        args: BaseModel,
        ctx: ToolContext,
    ) -> BaseModel | dict[str, Any]:
        raise NotImplementedError


def tool(
    key: str,
    *,
    description: str,
    default_deadline_ms: int = 30_000,
    max_result_bytes: int = 1_048_576,
) -> Callable[[type[ToolHandler]], type[ToolHandler]]:
    """Class decorator: declare a tool.

    The decorated class MUST subclass ``ToolHandler`` and define an inner
    ``Args`` model. The wire ``input_schema`` is derived from
    ``Args.model_json_schema()`` — Pydantic descriptions on
    ``Field(description=...)`` flow through onto the schema, so the LLM
    sees them.
    """

    def wrap(cls: type[ToolHandler]) -> type[ToolHandler]:
        if not isinstance(cls, type) or not issubclass(cls, ToolHandler):
            raise TypeError(f"@tool target {cls.__name__} must subclass ToolHandler")

        args_cls = getattr(cls, "Args", None)
        if args_cls is None or not (
            isinstance(args_cls, type) and issubclass(args_cls, BaseModel)
        ):
            raise TypeError(f"@tool {key}: class must define inner Args(BaseModel)")

        input_schema = args_cls.model_json_schema()

        output_schema: dict[str, Any]
        result_cls = getattr(cls, "Result", None)
        if result_cls is not None and isinstance(result_cls, type) and issubclass(
            result_cls, BaseModel
        ):
            output_schema = result_cls.model_json_schema()
        else:
            output_schema = {"type": "object"}

        cls.__vested_tool__ = ToolDeclaration(  # type: ignore[attr-defined]
            key=key,
            name=cls.__name__,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            default_deadline_ms=default_deadline_ms,
            max_result_bytes=max_result_bytes,
            handler_cls=cls,
        )
        return cls

    return wrap


def validate_args(decl: ToolDeclaration, raw: str) -> BaseModel:
    """Parse + validate raw JSON args against the tool's Args model.

    Raises ToolValidationError with the tool key on validation failure.
    """
    if decl.handler_cls is None:
        raise RuntimeError(f"tool {decl.key} has no handler_cls")
    args_model = decl.handler_cls.Args
    try:
        return args_model.model_validate_json(raw)
    except ValidationError as e:
        raise ToolValidationError(decl.key, str(e)) from e
