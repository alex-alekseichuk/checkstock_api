"""Repository for items (``stock.items``)."""

from __future__ import annotations

from uuid import UUID

from checkstock_api.common.db import Database
from checkstock_api.models.item import Item


class ItemRepo:
    """Data access for items, backed by the shared asyncpg pool."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def insert(self, sku: str, title: str, id: UUID | None = None) -> Item:
        """Insert a new item and return it.

        If ``id`` is given it is used as the primary key; otherwise the
        database default (``uuidv7``) generates it. ``created_at`` always
        comes from the database default.
        """
        if id is None:
            row = await self.db.pool.fetchrow(
                """
                INSERT INTO stock.items (sku, title)
                VALUES ($1, $2)
                RETURNING id, sku, title, created_at
                """,
                sku,
                title,
            )
        else:
            row = await self.db.pool.fetchrow(
                """
                INSERT INTO stock.items (id, sku, title)
                VALUES ($1, $2, $3)
                RETURNING id, sku, title, created_at
                """,
                id,
                sku,
                title,
            )
        return Item.from_row(row)
