"""Outer reconnect loop. Mirrors php-sdk ConnectorApp::runSwooleDaemon."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from vested_connect.errors import TokenError

from .backoff import Backoff
from .daemon import Daemon
from .dispatcher import Dispatcher
from .grpc_client import GrpcClient
from .signals import SignalHandler

if TYPE_CHECKING:
    from vested_connect.app import ConnectorApp

logger = logging.getLogger("vested_connect.supervisor")


async def run_supervised(
    app: ConnectorApp,
    token: str,
    host: str,
    port: int,
    insecure: bool = False,
) -> int:
    """Long-running supervisor.

    Wraps Daemon.run() in a reconnect-with-backoff loop. Exits only on
    SIGTERM/SIGINT (0) or terminal config errors (78). Otherwise retries
    forever with exponential backoff and jitter.
    """
    signals = SignalHandler()
    signals.install()
    backoff = Backoff()

    try:
        while not signals.should_exit():
            handshake_completed = False
            exit_code = 1
            try:
                async with GrpcClient(host, port, token, insecure=insecure) as client:
                    dispatcher = Dispatcher(app.tools, client)
                    daemon = Daemon(app, client, signals=signals, dispatcher=dispatcher)
                    exit_code = await daemon.run()
                    handshake_completed = daemon.handshake_completed
            except TokenError as e:
                logger.error("token rejected: %s", e)
                return 78
            except Exception as e:
                logger.warning("session ended with exception: %s", e)

            if signals.should_exit():
                return 0

            if exit_code == 78:
                return 78

            # exit_code 0 means the daemon exited cleanly (GoAway "shutdown"
            # or signal). Do not reconnect.
            if exit_code == 0:
                return 0

            if handshake_completed:
                backoff.reset()
            delay_ms = backoff.next()
            logger.warning(
                "hub session ended, reconnecting in %d ms (handshake_completed=%s, exit=%d)",
                delay_ms,
                handshake_completed,
                exit_code,
            )
            # Race the backoff sleep against a signal so SIGTERM during sleep
            # is caught — mirror PHP supervisor's signal-during-sleep coverage.
            try:
                await asyncio.wait_for(signals.wait(), timeout=delay_ms / 1000)
                # Signal arrived during sleep.
                return 0
            except asyncio.TimeoutError:
                pass
        return 0
    finally:
        signals.uninstall()
