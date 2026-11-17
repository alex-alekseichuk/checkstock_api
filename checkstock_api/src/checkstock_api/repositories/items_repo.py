"""Repository for items (``stock.items``)."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from checkstock_api.common.db import Database, tx
from checkstock_api.models.item import Item


class ItemRepo:
    """Data access for items, backed by the shared asyncpg pool."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def insert_item(self, sku: str, title: str, id: UUID | None = None) -> Item:
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

    @tx
    async def get_item_by_sku(
        self, sku: str, connection: asyncpg.Connection
    ) -> Item | None:
        """Fetch an item by its SKU, or ``None`` if no such item exists.

        ``connection`` is required: when the caller passes one (by keyword,
        for example from ``Database.transaction()``) the lookup runs on it;
        the :func:`~checkstock_api.common.db.tx` decorator acquires a
        connection from the pool when the argument is absent.
        """
        row = await connection.fetchrow(
            """
            SELECT id, sku, title, created_at
            FROM stock.items
            WHERE sku = $1
            """,
            sku,
        )
        return Item.from_row(row) if row is not None else None
