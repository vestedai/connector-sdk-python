"""Supervisor tests with a stubbed GrpcClient/Daemon — no real network."""

from __future__ import annotations

import pytest

from vested_connect.errors import TokenError
from vested_connect.runtime import supervisor as supervisor_mod


class _StubApp:
    @property
    def agents(self) -> list[object]:
        return []

    @property
    def tools(self) -> dict[str, object]:
        return {}


@pytest.mark.asyncio
async def test_supervisor_returns_78_on_token_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubClient:
        def __init__(self, *a: object, **kw: object) -> None:
            pass

        async def __aenter__(self) -> StubClient:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    class StubDaemon:
        def __init__(self, app: object, client: object, *, signals: object, **kw: object) -> None:
            self.handshake_completed = False

        async def run(self) -> int:
            raise TokenError("bad token")

    monkeypatch.setattr(supervisor_mod, "GrpcClient", StubClient)
    monkeypatch.setattr(supervisor_mod, "Daemon", StubDaemon)

    code = await supervisor_mod.run_supervised(_StubApp(), "tok", "host", 4443)
    assert code == 78


@pytest.mark.asyncio
async def test_supervisor_retries_then_exits_on_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: dict[str, int] = {"n": 0}

    class StubClient:
        def __init__(self, *a: object, **kw: object) -> None:
            pass

        async def __aenter__(self) -> StubClient:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    class StubDaemon:
        def __init__(self, app: object, client: object, *, signals: object, **kw: object) -> None:
            self.handshake_completed = False
            self._signals = signals

        async def run(self) -> int:
            attempts["n"] += 1
            if attempts["n"] == 2:
                # On second attempt, signal the supervisor.
                self._signals._event.set()  # type: ignore[attr-defined]
            return 1  # transient

    monkeypatch.setattr(supervisor_mod, "GrpcClient", StubClient)
    monkeypatch.setattr(supervisor_mod, "Daemon", StubDaemon)

    # Speed test by stubbing the Backoff to return 1ms delays.
    class FastBackoff:
        def next(self) -> int:
            return 1

        def reset(self) -> None:
            pass

    monkeypatch.setattr(supervisor_mod, "Backoff", FastBackoff)

    code = await supervisor_mod.run_supervised(_StubApp(), "tok", "host", 4443)
    assert code == 0
    assert attempts["n"] >= 2
