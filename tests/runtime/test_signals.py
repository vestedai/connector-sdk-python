import asyncio
import os
import signal

import pytest

from vested_connect.runtime.signals import SignalHandler


@pytest.mark.asyncio
async def test_install_uninstall_idempotent() -> None:
    h = SignalHandler()
    h.install()
    h.install()  # second call no-op
    assert h.should_exit() is False
    h.uninstall()
    h.uninstall()  # second call no-op


@pytest.mark.asyncio
async def test_sigterm_sets_event() -> None:
    h = SignalHandler()
    h.install()
    try:
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.sleep(0.05)  # let the loop process the signal
        assert h.should_exit() is True
    finally:
        h.uninstall()


@pytest.mark.asyncio
async def test_wait_resolves_on_signal() -> None:
    h = SignalHandler()
    h.install()
    try:
        async def fire_after() -> None:
            await asyncio.sleep(0.02)
            os.kill(os.getpid(), signal.SIGINT)

        task = asyncio.create_task(fire_after())
        await asyncio.wait_for(h.wait(), timeout=1.0)
        await task
    finally:
        h.uninstall()
