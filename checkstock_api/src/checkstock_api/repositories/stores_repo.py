"""Repository for stores (``stock.stores``)."""

from __future__ import annotations

from uuid import UUID

from checkstock_api.common.db import Database
from checkstock_api.models.store import Store, StoreStatus


class StoreRepo:
    """Data access for stores, backed by the shared asyncpg pool."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def insert(
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

    async def update(
        self,
        id: UUID,
        title: str | None = None,
        status: StoreStatus | None = None,
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
        row = await self.db.pool.fetchrow(
            f"""
            UPDATE stock.stores
            SET {", ".join(sets)}
            WHERE id = ${len(args)}
            RETURNING id, title, status, created_at
            """,
            *args,
        )
        return Store.from_row(row) if row is not None else None
