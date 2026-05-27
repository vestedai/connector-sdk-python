"""Walk a Python module / package; collect every @agent and @tool class."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from vested_connect.agent import AgentDeclaration
from vested_connect.tool import ToolDeclaration


def scan_module(module_path: str) -> tuple[list[AgentDeclaration], dict[str, ToolDeclaration]]:
    """Walk a module + submodules; collect every decorated agent / tool.

    Returns (agents_list, tools_dict_keyed_by_tool_key).
    Raises RuntimeError on duplicate tool keys.
    """
    agents: list[AgentDeclaration] = []
    tools: dict[str, ToolDeclaration] = {}

    root = importlib.import_module(module_path)
    _collect(root, agents, tools)

    if hasattr(root, "__path__"):
        for info in pkgutil.walk_packages(root.__path__, prefix=f"{module_path}."):
            mod = importlib.import_module(info.name)
            _collect(mod, agents, tools)

    return agents, tools


def _collect(
    mod: Any,
    agents: list[AgentDeclaration],
    tools: dict[str, ToolDeclaration],
) -> None:
    for name in dir(mod):
        obj = getattr(mod, name, None)
        if not isinstance(obj, type):
            continue

        a = getattr(obj, "__vested_agent__", None)
        if isinstance(a, AgentDeclaration):
            if a not in agents:  # avoid duplicate when scanning re-exports
                agents.append(a)

        t = getattr(obj, "__vested_tool__", None)
        if isinstance(t, ToolDeclaration):
            if t.key in tools and tools[t.key] is not t:
                raise RuntimeError(
                    f"duplicate tool key {t.key} (handlers: {tools[t.key].name} and {t.name})"
                )
            tools[t.key] = t
