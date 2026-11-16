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
                    id, item_id, quantity, type, src_stock_id, dest_stock_id,
                    status, created_at, updated_at
                """,
                transfer.item_id,
                transfer.quantity,
                transfer.type.value,
                transfer.src_stock_id,
                transfer.dest_stock_id,
                transfer.status.value,
            )
        else:
            row = await connection.fetchrow(
                """
                INSERT INTO stock.transfers
                    (id,item_id, quantity, type, src_stock_id, dest_stock_id, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING
                    id, item_id, quantity, type, src_stock_id, dest_stock_id,
                    status, created_at, updated_at
                """,
                transfer.id,
                transfer.item_id,
                transfer.quantity,
                transfer.type.value,
                transfer.src_stock_id,
                transfer.dest_stock_id,
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
