"""Repository for stores (``stock.stores``)."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from checkstock_api.common.db import Database, tx
from checkstock_api.models.store import Store, StoreStatus


class StoreRepo:
    """Data access for stores, backed by the shared asyncpg pool."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def insert_store(
        self,
        title: str,
        status: StoreStatus = StoreStatus.ACTIVE,
        id: UUID | None = None,
    ) -> Store:
        """Insert a new store and return it.

        If ``id`` is given it is used as the primary key; otherwise the
        database default (``uuidv7``) generates it. ``status`` defaults to
        ``active`` and ``created_at`` always comes from the database default.
        """
        if id is None:
            row = await self.db.pool.fetchrow(
                """
                INSERT INTO stock.stores (title, status)
                VALUES ($1, $2)
                RETURNING id, title, status, created_at
                """,
                title,
                status.value,
            )
        else:
            row = await self.db.pool.fetchrow(
                """
                INSERT INTO stock.stores (id, title, status)
                VALUES ($1, $2, $3)
                RETURNING id, title, status, created_at
                """,
                id,
                title,
                status.value,
            )
        return Store.from_row(row)

    async def lock_store(
        self,
        connection: asyncpg.Connection,
        id: UUID,
    ) -> Store | None:
        """Fetch a store by id on the given connection (inside an open
        transaction), or ``None`` if no such store exists.

        The ``FOR UPDATE`` row lock serializes concurrent status changes
        of the store for the duration of the caller's transaction.
        """
        row = await connection.fetchrow(
            """
            SELECT id, title, status, created_at
            FROM stock.stores
            WHERE id = $1
            FOR UPDATE
            """,
            id,
        )
        return Store.from_row(row) if row is not None else None

    @tx
    async def update_store(
        self,
        id: UUID,
        title: str | None = None,
        status: StoreStatus | None = None,
        connection: asyncpg.Connection | None = None,
    ) -> Store | None:
        """Update an existing store, changing only the fields that are given.

        Returns the updated store, or ``None`` if no store with ``id``
        exists. Raises ``ValueError`` if neither ``title`` nor ``status``
        is provided.
        """
        sets: list[str] = []
        args: list[object] = []
        if title is not None:
            args.append(title)
            sets.append(f"title = ${len(args)}")
        if status is not None:
            args.append(status.value)
            sets.append(f"status = ${len(args)}")
        if not sets:
            raise ValueError("nothing to update: pass title and/or status")
        args.append(id)
        row = await connection.fetchrow(
            f"""
            UPDATE stock.stores
            SET {", ".join(sets)}
            WHERE id = ${len(args)}
            RETURNING id, title, status, created_at
            """,
            *args,
        )
        return Store.from_row(row) if row is not None else None
