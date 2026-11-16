"""Repository for on-hand stock (``stock.stock``)."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from asyncpg import Record

from checkstock_api.common.db import Database
from checkstock_api.models.stock import Stock
from checkstock_api.models.store import StoreStatus
from checkstock_api.models.transfer import TransferStatus, TransferType


class StockRepo:
    """Data access for on-hand stock, backed by the shared asyncpg pool."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def list_stock(self) -> list[Record]:
        """List stock rows with ``quantity > 0`` at active stores.

        Each row contains the item's ``id``/``sku``/``title``, the store's
        ``id``/``title``, ``quantity``, ``reserved`` and ``available``
        (``quantity - reserved``), sorted by ``sku`` then store ``title``.
        """
        return await self.db.pool.fetch(
            f"""
            SELECT
                i.id                    AS item_id,
                i.sku                   AS item_sku,
                i.title                 AS item_title,
                s.id                    AS store_id,
                s.title                 AS store_title,
                st.quantity,
                st.reserved,
                st.quantity - st.reserved AS available
            FROM stock.stock st
            JOIN stock.items  i ON i.id = st.item_id
            JOIN stock.stores s ON s.id = st.store_id
            WHERE st.quantity > 0
              AND s.status = '{StoreStatus.ACTIVE.value}'
            ORDER BY i.sku ASC, s.title ASC
            """,
        )

    # The only transfer types that can appear in transit (``inbound`` is
    # excluded from this report).
    _IN_TRANSIT_TYPES = (
        TransferType.TRANSFER.value,
        TransferType.SHIP_FBO.value,
        TransferType.SHIP_FBS.value,
    )

    async def list_in_transit(
        self, transfer_type: TransferType | None = None
    ) -> list[Record]:
        """List in-transit transfers, optionally filtered by ``transfer_type``.

        Only the ``transfer``, ``ship_fbo`` and ``ship_fbs`` types are
        reported (``inbound`` is excluded); when ``transfer_type`` is given
        the result is narrowed to that single type.

        Each row contains the item's ``id``/``sku``/``title``, the source
        store's ``id``/``title``, the destination store's ``id``/``title``,
        ``quantity``, ``type`` and ``updated_at`` (renamed to ``departed_at``),
        sorted by ``sku`` then ``departed_at``. Source/destination stores are
        optional, so they are left-joined and may be ``None``.
        """
        types = (
            transfer_type.value
            if transfer_type is not None
            else "','".join(self._IN_TRANSIT_TYPES)
        )
        return await self.db.pool.fetch(
            f"""
            SELECT
                i.id                    AS item_id,
                i.sku                   AS item_sku,
                i.title                 AS item_title,
                src.id                  AS source_store_id,
                src.title               AS source_store_title,
                dst.id                  AS dest_store_id,
                dst.title               AS dest_store_title,
                t.quantity,
                t.type,
                t.updated_at            AS departed_at
            FROM stock.transfers t
            JOIN stock.items   i   ON i.id = t.item_id
            LEFT JOIN stock.stores src ON src.id = t.src_stock_id
            LEFT JOIN stock.stores dst ON dst.id = t.dest_stock_id
            WHERE t.status = '{TransferStatus.IN_TRANSIT.value}'
              AND t.type IN ('{types}')
            ORDER BY i.sku ASC, t.updated_at ASC
            """,
        )

    async def lock_stock(
        self,
        connection: asyncpg.Connection,
        item_id: UUID,
        store_id: UUID,
    ) -> Stock | None:
        """Fetch the ``(item_id, store_id)`` stock row with a row lock,
        or ``None`` if the item has no stock row at that store.

        The ``FOR UPDATE`` lock serializes concurrent modifications of the
        row for the duration of the caller's transaction.
        """
        row = await connection.fetchrow(
            """
            SELECT item_id, store_id, quantity, reserved, created_at
            FROM stock.stock
            WHERE item_id = $1 AND store_id = $2
            FOR UPDATE
            """,
            item_id,
            store_id,
        )
        return Stock.from_row(row) if row is not None else None

    async def create_lock_stock(
        self,
        connection: asyncpg.Connection,
        item_id: UUID,
        store_id: UUID,
    ) -> Stock:
        """Insert the ``(item_id, store_id)`` stock row, or return the
        existing row if one is already present.

        On a primary-key conflict (two concurrent receipts of the same
        item at the same store) the existing row is returned with its
        row lock held for the duration of the caller's transaction, so
        the caller can safely adjust it.
        """
        row = await connection.fetchrow(
            """
            INSERT INTO stock.stock AS existing
                (item_id, store_id)
            VALUES ($1, $2)
            ON CONFLICT (item_id, store_id) DO UPDATE
                SET quantity = existing.quantity,
                    reserved = existing.reserved
            RETURNING item_id, store_id, quantity, reserved, created_at
            """,
            item_id,
            store_id,
        )
        return Stock.from_row(row)

    async def save_stock(
        self,
        connection: asyncpg.Connection,
        stock: Stock,
    ) -> None:
        """Update the existing ``(item_id, store_id)`` stock row in place.

        Only an existing row is updated (the row is never created); the
        caller must have locked it with :meth:`lock_stock` first, and
        ``stock`` carries the new values to store. The guarded update
        keeps the table's CHECK constraints satisfiable. Raises
        ``ValueError`` when no row is updated.
        """
        result = await connection.execute(
            """
            UPDATE stock.stock
            SET quantity = $3,
                reserved = $4
            WHERE item_id = $1
              AND store_id = $2
              AND $3 >= 0
              AND $4 >= 0
              AND $3 >= $4
            """,
            stock.item_id,
            stock.store_id,
            stock.quantity,
            stock.reserved,
        )
        if result == "UPDATE 0":
            raise ValueError(
                "no updatable stock row for the item at the store"
            )
