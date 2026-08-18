"""Resolves which tools each agent gets.

THE ONLY PLACE THIS IS DECIDED. Both the Register frame (runtime/daemon.py) and
the baseline fingerprint (runtime/fingerprint.py) call :func:`resolve_bindings`.
Deriving binding separately in each is how a fingerprint comes to disagree with
the frame it summarises — and the hub trusts the fingerprint to decide whether
to reconcile at all, so a disagreement means a registration whose content
changed gets short-circuited as unchanged. Nothing errors; the change simply
never happens.

The rule: an empty ``agents`` means the historical namespace-prefix binding. A
non-empty one is AUTHORITATIVE — the prefix confers nothing once a list is
present.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .errors import ConnectorError

#: Binds to every agent this connector declares.
ALL_AGENTS = "*"


def resolve_bindings(
    agents: Sequence[Any], tools: dict[str, Any]
) -> dict[str, list[Any]]:
    """agent key -> its tools, each list ordinally sorted.

    Ordinal because the fingerprint hashes the result and it is the only
    ordering the other SDKs agree on.
    """
    bound: dict[str, list[Any]] = {a.key: [] for a in agents}

    for tool in tools.values():
        for agent_key in _targets_for(tool, agents):
            if agent_key in bound:
                bound[agent_key].append(tool)

    for items in bound.values():
        items.sort(key=lambda t: t.key)

    return bound


def _targets_for(tool: Any, agents: Sequence[Any]) -> list[str]:
    """The prefix rule when the tool names none, every agent for "*", else the list."""
    declared = tuple(getattr(tool, "agents", ()) or ())

    if not declared:
        return [a.key for a in agents if tool.key.startswith(a.key + ".")]
    if ALL_AGENTS in declared:
        return [a.key for a in agents]
    return list(declared)


def validate_bindings(
    agents: Sequence[Any],
    tools: dict[str, Any],
    warn: Callable[[str], None],
) -> None:
    """Refuses what cannot be meant; warns about what is legal but surprising.

    ``warn`` is separate from raising so the caller routes messages to its own
    logger, and so tests can assert on them.
    """
    declared_agents = {a.key for a in agents}
    known = ", ".join(sorted(declared_agents))

    for tool in tools.values():
        listed = tuple(getattr(tool, "agents", ()) or ())

        if not listed:
            # No list, so the prefix must find an agent — otherwise nothing
            # could ever call this tool, which is never intentional. This rule
            # applies only to tools naming no agents: one that names its agents
            # is legitimately allowed to sit outside all of their namespaces.
            if not any(tool.key.startswith(a.key + ".") for a in agents):
                raise ConnectorError(
                    f"tool '{tool.key}' has no matching agent (key must start "
                    f"with '<agent_key>.'), and declares no agents to bind it "
                    f"explicitly. Declared agents: {known}."
                )
            continue

        has_star = ALL_AGENTS in listed
        if has_star and len(listed) > 1:
            explicit = ", ".join(a for a in listed if a != ALL_AGENTS)
            raise ConnectorError(
                f'@tool("{tool.key}") combines "{ALL_AGENTS}" with explicit '
                f'agent keys ({explicit}). "{ALL_AGENTS}" already means every '
                f"agent; drop one or the other."
            )
        if has_star:
            continue

        for key in listed:
            if key not in declared_agents:
                raise ConnectorError(
                    f'@tool("{tool.key}") names agent "{key}", which this '
                    f"connector does not declare. Declared agents: {known}."
                )

        # Legal, and easy to reach by accident: the key says one agent owns the
        # tool while the list says that agent cannot call it. Warn rather than
        # raise — it is exactly how you express "lives here, callable from there".
        for a in agents:
            if tool.key.startswith(a.key + ".") and a.key not in listed:
                warn(
                    f"{tool.key} declares agents [{', '.join(listed)}] and is "
                    f"therefore NOT available to {a.key}; rename the key or add "
                    f"it to the list."
                )


def validate_hub_limits(
    bound: dict[str, list[Any]],
    max_tools_per_agent: int,
) -> None:
    """Refuse a binding the hub would reject for exceeding max_tools_per_agent.

    NOT callable from build(), and that is not an oversight: the limit is
    per-connector and arrives in HelloAck (proto field 5), which the hub sends
    only after the worker dials it. This runs at the one point where the limit
    is known and the frame is not yet sent — between HelloAck and Register.

    Worth checking even though the hub rejects anyway: a rejected Register
    leaves the hub holding a stream with NO declaration for the connector, and
    both the schema gate and the credential gate then refuse every call —
    reported as ``lookup_failed``, whose message is "try again shortly", advice
    that can never work when the cause is a permanent validation failure.
    Measured on erp_bc 2026-08-18: one agent went from 30 tools to 31 when a
    shared tool was bound with "*", and that single tool cost ~1 hour of
    refusals across BOTH gates.

    The hub reports the offender as ``agents[5].tools`` — an index into the wire
    frame. This names the agent, and names the shared tools when any contributed.

    ``max_tools_per_agent`` of 0 MEANS UNKNOWN and is skipped: proto3 defaults a
    uint32 to 0 and an older hub sends no value, so treating 0 as a real ceiling
    would ground every connector against a hub that never set one.
    """
    if not max_tools_per_agent:
        return

    for agent_key, tools in bound.items():
        if len(tools) <= max_tools_per_agent:
            continue

        shared = sorted(t.key for t in tools if tuple(getattr(t, "agents", ()) or ()))
        because = (
            f" Bound across agents by their own declaration: {', '.join(shared)}. "
            'A tool bound with "*" lands on every agent, including this one.'
            if shared
            else ""
        )

        raise ConnectorError(
            f'Agent "{agent_key}" would declare {len(tools)} tools; this '
            f"connector's hub limit is {max_tools_per_agent}. The hub would refuse "
            f"the whole Register, leaving it with no declaration for this connector "
            f"— which makes both the schema gate and the credential gate refuse "
            f"every call.{because}"
        )
