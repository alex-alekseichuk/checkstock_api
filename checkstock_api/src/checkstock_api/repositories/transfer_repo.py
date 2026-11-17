"""Repository for transfers (``stock.transfers`` and ``stock.transfer_logs``)."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from checkstock_api.common.db import Database
from checkstock_api.models.transfer import Transfer, TransferEvent
from checkstock_api.models.transfer_log import TransferLog


class TransferRepo:
    """Data access for transfers and their event log, backed by the shared asyncpg pool."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def lock_transfer(
        self,
        connection: asyncpg.Connection,
        id: UUID,
    ) -> Transfer | None:
        """Fetch a transfer by id on the given connection (inside an open
        transaction), or ``None`` if no such transfer exists.

        The ``FOR UPDATE`` row lock serializes concurrent state changes of
        the transfer for the duration of the caller's transaction.
        """
        row = await connection.fetchrow(
            """
            SELECT id, item_id, quantity, type,
                   src_stock_id  AS src_store_id,
                   dest_stock_id AS dest_store_id,
                   status, created_at, updated_at
            FROM stock.transfers
            WHERE id = $1
            FOR UPDATE
            """,
            id,
        )
        return Transfer.from_row(row) if row is not None else None

    async def update_transfer(
        self,
        connection: asyncpg.Connection,
        transfer: Transfer,
    ) -> Transfer:
        """Update a transfer's status in place on the given connection
        (inside an open transaction) and return the updated transfer.

        The caller must hold the row lock from :meth:`lock_transfer`;
        ``updated_at`` is set to the current time by the ``UPDATE``.
        """
        row = await connection.fetchrow(
            """
            UPDATE stock.transfers
            SET status = $2,
                updated_at = now()
            WHERE id = $1
            RETURNING
                id, item_id, quantity, type,
                src_stock_id  AS src_store_id,
                dest_stock_id AS dest_store_id,
                status, created_at, updated_at
            """,
            transfer.id,
            transfer.status.value,
        )
        return Transfer.from_row(row)

    async def insert_transfer(
        self,
        connection: asyncpg.Connection,
        transfer,
    ) -> Transfer:
        """Insert a new transfer on the given connection (inside an open
        transaction) and return it.
        """
        if transfer.id is None:
            row = await connection.fetchrow(
                """
                INSERT INTO stock.transfers
                    (item_id, quantity, type, src_stock_id, dest_stock_id, status)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING
                    id, item_id, quantity, type,
                    src_stock_id  AS src_store_id,
                    dest_stock_id AS dest_store_id,
                    status, created_at, updated_at
                """,
                transfer.item_id,
                transfer.quantity,
                transfer.type.value,
                transfer.src_store_id,
                transfer.dest_store_id,
                transfer.status.value,
            )
        else:
            row = await connection.fetchrow(
                """
                INSERT INTO stock.transfers
                    (id,item_id, quantity, type, src_stock_id, dest_stock_id, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING
                    id, item_id, quantity, type,
                    src_stock_id  AS src_store_id,
                    dest_stock_id AS dest_store_id,
                    status, created_at, updated_at
                """,
                transfer.id,
                transfer.item_id,
                transfer.quantity,
                transfer.type.value,
                transfer.src_store_id,
                transfer.dest_store_id,
                transfer.status.value,
            )
        return Transfer.from_row(row)

    async def insert_log(
        self,
        connection: asyncpg.Connection,
        transfer_id: UUID,
        event: TransferEvent,
    ) -> TransferLog:
        """Record one state-change event for a transfer on the given
        connection (inside an open transaction) and return it.
        """
        row = await connection.fetchrow(
            """
            INSERT INTO stock.transfer_logs (transfer_id, event)
            VALUES ($1, $2)
            RETURNING id, transfer_id, event, logged_at
            """,
            transfer_id,
            event.value,
        )
        return TransferLog.from_row(row)
