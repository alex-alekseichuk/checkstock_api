"""asyncpg connection pool wrapper, shared across the app."""

from __future__ import annotations

import asyncpg


class Database:
    """Holds the asyncpg pool for the checkstock database.

    Usage::

        db = Database("postgresql://user:pass@host:5432/checkstock")
        await db.connect()
        ...
        await db.close()

    or as an async context manager::

        async with Database(dsn) as pool:
            ...
    """

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        """The live pool; raises if :meth:`connect` was not called yet."""
        if self._pool is None:
            raise RuntimeError("Database is not connected; call connect() first")
        return self._pool

    async def connect(self) -> asyncpg.Pool:
        """Create the pool on first call and return it (idempotent)."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=self.min_size,
                max_size=self.max_size,
            )
        return self._pool

    async def close(self) -> None:
        """Close the pool and drop the reference."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def __aenter__(self) -> asyncpg.Pool:
        return await self.connect()

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
