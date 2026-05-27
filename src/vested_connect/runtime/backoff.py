"""Exponential backoff with jitter — port of php-sdk Hub\\Backoff."""

from __future__ import annotations

import random


class Backoff:
    """Exponential backoff: initial_ms doubles each next() up to cap_ms,
    with ±jitter_pct% additive jitter on each return.

    Mirrors vested-ai-sdks/php/src/Vested/Connect/Sdk/Hub/Backoff.php
    so v0.2.4's supervisor semantics carry over identically.
    """

    def __init__(self, initial_ms: int = 1000, cap_ms: int = 30_000, jitter_pct: int = 20) -> None:
        self.initial_ms = initial_ms
        self.cap_ms = cap_ms
        self.jitter_pct = jitter_pct
        self._current = initial_ms

    def next(self) -> int:
        base = min(self._current, self.cap_ms)
        self._current = min(self._current * 2, self.cap_ms)
        if self.jitter_pct == 0:
            return base
        spread = base * self.jitter_pct // 100
        return max(0, base + random.randint(-spread, spread))

    def reset(self) -> None:
        self._current = self.initial_ms
