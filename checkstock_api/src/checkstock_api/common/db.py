"""asyncpg connection pool wrapper, shared across the app."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any

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

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a dedicated connection and run inside a transaction.

        All statements issued on the yielded connection run in one
        transaction: it commits when the block exits normally and rolls
        back if an exception propagates::

            async with db.transaction() as connection:
                await connection.execute(...)
        """
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                yield connection


def tx(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator making a repo method's ``connection`` argument optional.

    The decorated function must declare ``connection`` as its last
    argument. When the caller passes a connection (by keyword), it is used
    as-is — for example inside ``Database.transaction()``; when it is
    absent, a connection is acquired from ``self.db.pool`` for the
    duration of the call::

        @tx
        async def get_by_sku(
            self, sku: str, connection: asyncpg.Connection
        ) -> Item | None:
            ...

        await repo.get_by_sku(sku)                  # pool connection
        async with db.transaction() as connection:
            await repo.get_by_sku(sku, connection=connection)
    """

    @wraps(func)
    async def wrapper(
        self,
        *args,
        connection: asyncpg.Connection | None = None,
        **kwargs,
    ) -> Any:
        if connection is None:
            async with self.db.pool.acquire() as conn:
                return await func(self, *args, conn, **kwargs)
        return await func(self, *args, connection, **kwargs)

    return wrapper
