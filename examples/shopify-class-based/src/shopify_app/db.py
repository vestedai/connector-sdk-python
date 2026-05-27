"""Optional asyncpg connection pool for direct analytics-replica queries.

This module lazily creates a single module-level pool the first time
get_pool() is called. The pool is reused for the lifetime of the Python
process — which is correct for a long-running worker.

Note: the SDK does not yet expose a lifecycle hook for shared resources,
so pool clean-up on shutdown is best-effort (the OS reclaims sockets when
the process exits).

Usage::

    pool = await get_pool()          # None if DATABASE_URL is unset
    if pool is None:
        raise ToolValidationError(...)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT ...")
"""

from __future__ import annotations

import os

try:
    import asyncpg  # type: ignore[import]

    _asyncpg_available = True
except ImportError:
    _asyncpg_available = False

_pool: asyncpg.Pool | None = None  # type: ignore[name-defined]  # module-level singleton


async def get_pool() -> asyncpg.Pool | None:  # type: ignore[name-defined]
    """Return (or lazily create) the asyncpg pool.

    Returns None when DATABASE_URL is unset or asyncpg is not installed.
    The pool is created with min_size=1, max_size=5 — suitable for the
    typical single-replica analytics use case.
    """
    global _pool  # noqa: PLW0603

    if not _asyncpg_available:
        return None

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return None

    if _pool is None:
        _pool = await asyncpg.create_pool(  # type: ignore[attr-defined]
            dsn=database_url,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )

    return _pool
