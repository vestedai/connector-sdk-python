"""Top-level container. Customers build one in bootstrap.py and the CLI runs it."""

from __future__ import annotations

import logging

from .agent import AgentDeclaration
from .runtime.scanner import scan_module
from .runtime.supervisor import run_supervised
from .tool import ToolDeclaration
from .tool_binding import validate_bindings


class ConnectorApp:
    """The customer-facing container.

    Built by the customer's bootstrap.py and consumed by the
    `vested-connect worker` CLI. Holds the agent + tool registries
    and exposes .run() which drives the supervised daemon loop.

    Example bootstrap.py::

        from vested_connect import ConnectorApp

        app = (
            ConnectorApp.create()
            .scan_module("acme_commerce.agents")
            .scan_module("acme_commerce.tools")
        )
    """

    def __init__(self) -> None:
        self._agents: list[AgentDeclaration] = []
        self._tools: dict[str, ToolDeclaration] = {}
        self._logger: logging.Logger = logging.getLogger("vested_connect")

    @classmethod
    def create(cls) -> ConnectorApp:
        return cls()

    def with_logger(self, logger: logging.Logger) -> ConnectorApp:
        self._logger = logger
        return self

    def scan_module(self, module_path: str) -> ConnectorApp:
        """Walk a Python package and collect every @agent / @tool.

        Multiple scan_module() calls accumulate. Duplicate agent keys or
        tool keys raise RuntimeError.
        """
        agents, tools = scan_module(module_path)
        for a in agents:
            if any(existing.key == a.key for existing in self._agents):
                raise RuntimeError(f"duplicate agent key {a.key} (already registered)")
            self._agents.append(a)
        for k, v in tools.items():
            if k in self._tools:
                raise RuntimeError(f"duplicate tool key {k}")
            self._tools[k] = v
        return self

    @property
    def agents(self) -> list[AgentDeclaration]:
        return list(self._agents)

    @property
    def tools(self) -> dict[str, ToolDeclaration]:
        return dict(self._tools)

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    async def run(self, token: str, hub: str, insecure: bool = False) -> int:
        """Run the supervised connector worker.

        hub is "host:port"; insecure=True uses plaintext gRPC (local dev only).
        Returns the supervisor's exit code: 0 (signal) / 78 (token rejected).
        """
        # Refuses an agent key this connector does not declare, "*" mixed with
        # explicit keys, and a tool that neither matches an agent namespace nor
        # names any agent. Here rather than in scan_module(): that accumulates
        # across calls, so validating there would reject a tool declared before
        # its agent. This is the last point before the worker dials the hub.
        validate_bindings(self._agents, self._tools, self._logger.warning)

        host, _, port_str = hub.partition(":")
        port = int(port_str) if port_str else 4443
        return await run_supervised(self, token, host, port, insecure=insecure)
