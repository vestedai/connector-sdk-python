"""@agent decorator + Instruction + AgentDeclaration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T", bound=type)


@dataclass(frozen=True, slots=True)
class Instruction:
    """One system / task / persona block at a stable position.

    The composer at run-time concatenates instructions by ascending
    position. position is the stable join key for admin overrides —
    keep it monotonic across versions when possible.
    """

    type: str
    position: int
    body: str
    format: str = "markdown"


@dataclass
class AgentDeclaration:
    """What the @agent decorator stamps onto a class.

    Captured at import time; the runtime scanner picks these up and
    sends them in the Register frame.
    """

    key: str
    name: str
    model: str
    description: str = ""
    status: str = "active"
    instructions: list[Instruction] = field(default_factory=list)
    model_config: dict[str, object] = field(default_factory=dict)


def agent(
    *,
    key: str,
    name: str,
    model: str,
    description: str = "",
    status: str = "active",
    instructions: list[Instruction] | None = None,
    model_config: dict[str, object] | None = None,
) -> Callable[[T], T]:
    """Class decorator: declare an agent.

    The decorated class is a marker — its only role is to anchor the
    declaration. Tools that belong to this agent are matched separately
    by their tool_key namespace prefix.

    Example::

        @agent(
            key="acme.insights",
            name="Insights",
            model="openai:gpt-4o",
            instructions=[Instruction(type="system", position=0, body="You are…")],
        )
        class Insights:
            pass
    """

    def wrap(cls: T) -> T:
        cls.__vested_agent__ = AgentDeclaration(  # type: ignore[attr-defined]
            key=key,
            name=name,
            model=model,
            description=description,
            status=status,
            instructions=list(instructions or []),
            model_config=dict(model_config or {}),
        )
        return cls

    return wrap
