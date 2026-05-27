"""Translate SIGTERM/SIGINT into an asyncio.Event the supervisor polls."""

from __future__ import annotations

import asyncio
import signal


class SignalHandler:
    """SIGTERM/SIGINT → asyncio.Event.

    install() / uninstall() are idempotent. The supervisor calls install()
    at startup and uninstall() on graceful exit. Inside the supervisor's
    inter-attempt sleep, `await asyncio.wait_for(signals.wait(), timeout=…)`
    races the sleep against the signal so SIGTERM during backoff is caught.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._installed = False

    def install(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        if self._installed:
            return
        loop = loop or asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._event.set)
        self._installed = True

    def uninstall(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        if not self._installed:
            return
        loop = loop or asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)
        self._installed = False

    def should_exit(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()
