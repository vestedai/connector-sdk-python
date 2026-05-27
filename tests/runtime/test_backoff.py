from vested_connect.runtime.backoff import Backoff


def test_exponential_progression_no_jitter() -> None:
    b = Backoff(initial_ms=1000, cap_ms=30_000, jitter_pct=0)
    assert b.next() == 1000
    assert b.next() == 2000
    assert b.next() == 4000
    assert b.next() == 8000
    assert b.next() == 16_000
    assert b.next() == 30_000
    assert b.next() == 30_000  # capped


def test_reset_returns_to_initial() -> None:
    b = Backoff(initial_ms=1000, cap_ms=30_000, jitter_pct=0)
    b.next()
    b.next()
    b.next()
    b.reset()
    assert b.next() == 1000


def test_jitter_stays_within_bounds() -> None:
    b = Backoff(initial_ms=1000, cap_ms=30_000, jitter_pct=20)
    for _ in range(50):
        v = b.next()
        b.reset()
        assert 800 <= v <= 1200, f"out of jitter range: {v}"
