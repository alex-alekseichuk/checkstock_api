"""Service layer for transfers, on top of the item/store/stock/transfer repos.

Each operation is a unit of work inside one transaction: the transfer row
and the affected stock rows are locked, the state is checked, the stock
effects are applied, and the status change together with its event log is
saved.

- ``create_transfer`` validates the type against the given stores and
  applies the initial stock effects.
- ``receive_transfer`` moves an ``in_transit`` transfer to ``received`` and
  credits the destination store's stock.
- ``cancel_transfer`` moves a ``reserved`` shipment to ``canceled`` and
  releases the stock reserved at the source store.
- ``approve_transfer`` moves a ``reserved`` shipment to ``in_transit`` and
  lets the reserved goods leave the source store.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from checkstock_api.common.db import Database
from checkstock_api.models.store import StoreStatus
from checkstock_api.models.transfer import (
    Transfer,
    TransferType,
    TransferError,
)
from checkstock_api.repositories.items_repo import ItemRepo
from checkstock_api.repositories.stores_repo import StoreRepo
from checkstock_api.repositories.stock_repo import StockRepo
from checkstock_api.repositories.transfer_repo import TransferRepo


class TransferService:
    """Business operations for transfers."""

    def __init__(
        self,
        db: Database,
        items_repo: ItemRepo,
        stores_repo: StoreRepo,
        stock_repo: StockRepo,
        transfers_repo: TransferRepo,
    ) -> None:
        self.db = db
        self.items_repo = items_repo
        self.stores_repo = stores_repo
        self.stock_repo = stock_repo
        self.transfers_repo = transfers_repo

    async def create_transfer(
        self,
        type: TransferType,
        sku: str,
        quantity: int,
        source_store_id: UUID | None = None,
        dest_store_id: UUID | None = None,
        id: UUID | None = None,
    ) -> Transfer:
        """Create a transfer and apply its stock effects atomically.
        Validation inside the transaction.
        """

        async with self.db.transaction() as connection:
            item = await self.items_repo.get_item_by_sku(sku)
            if item is None:
                raise TransferError(404, f"item with sku {sku!r} not found")

            # Lock the involved stores and stock rows in ascending
            # store-id order: concurrent transfers then acquire the same
            # locks in the same order (no deadlock between e.g. A->B and
            # B->A), and a store cannot be closed out from under a
            # transfer being created.
            store_ids = sorted(
                {sid for sid in (source_store_id, dest_store_id) if sid is not None}
            )
            for store_id in store_ids:
                store = await self.stores_repo.lock_store(connection, store_id)
                if store is None or store.status != StoreStatus.ACTIVE:
                    raise TransferError(404, f"store with id {store_id!r} not found")

            stocks = {}
            for store_id in store_ids:
                stock = await self.stock_repo.lock_stock(connection, item.id, store_id)
                if stock is None and store_id == dest_store_id and (
                    type == TransferType.INBOUND or type == TransferType.TRANSFER
                ):
                    stock = await self.stock_repo.create_lock_stock(
                        connection, item.id, store_id
                    )
                stocks[store_id] = stock

            src_stock = stocks[source_store_id] if source_store_id is not None else None
            dest_stock = stocks[dest_store_id] if dest_store_id is not None else None

            event, transfer = Transfer.create(
                type=type,
                item_id=item.id,
                quantity=quantity,
                src_stock=src_stock,
                dest_stock=dest_stock,
                id=id
            )

            if event is None:
                raise TransferError(500, f"Can't create a transfer type: {type!r}")

            transfer = await self.transfers_repo.insert_transfer(
                connection,
                transfer
            )

            if (type == TransferType.TRANSFER or type == TransferType.SHIP_FBO or type == TransferType.SHIP_FBS) and (src_stock is not None):
                await self.stock_repo.update_stock(connection, src_stock)

            if (type == TransferType.INBOUND) and (dest_stock is not None):
                await self.stock_repo.update_stock(connection, dest_stock)

            await self.transfers_repo.insert_log(connection, transfer.id, event)

            return transfer

    async def receive_transfer(self, transfer_id: UUID) -> Transfer:
        """Receive an in-transit transfer: the goods arrive at the
        destination store (when the transfer has one) and the transfer
        reaches its final ``received`` state.
        """

        async with self.db.transaction() as connection:
            transfer = await self._lock_transfer_with_stock(connection, transfer_id)
            event = transfer.receive()
            if event is None:
                raise TransferError(409, f"Can't receive a transfer id: {transfer_id!r}")

            await self._save_transfer_with_stock(connection, transfer)
            await self.transfers_repo.insert_log(connection, transfer.id, event)

            return transfer

    async def cancel_transfer(self, transfer_id: UUID) -> Transfer:
        """Cancel a reserved FBS shipment: the reservation of the source
        store's stock is released and the transfer reaches the final
        ``canceled`` state.
        """

        async with self.db.transaction() as connection:
            transfer = await self._lock_transfer_with_stock(connection, transfer_id)
            event = transfer.cancel()
            if event is None:
                raise TransferError(409, f"Can't cancel a transfer id: {transfer_id!r}")

            await self._save_transfer_with_stock(connection, transfer)
            await self.transfers_repo.insert_log(connection, transfer.id, event)

            return transfer

    async def approve_transfer(self, transfer_id: UUID) -> Transfer:
        """Approve a reserved FBS shipment: the reserved goods leave the
        source store and the transfer goes into transit.
        """

        async with self.db.transaction() as connection:
            transfer = await self._lock_transfer_with_stock(connection, transfer_id)
            event = transfer.approve()
            if event is None:
                raise TransferError(409, f"Can't approve a transfer id: {transfer_id!r}")

            await self._save_transfer_with_stock(connection, transfer)
            await self.transfers_repo.insert_log(connection, transfer.id, event)

            return transfer

    async def _lock_transfer_with_stock(self, connection: asyncpg.Connection, transfer_id: UUID) -> Transfer:
        transfer = await self.transfers_repo.lock_transfer(connection, transfer_id)
        if transfer is None:
            raise TransferError(
                404, f"transfer with id {transfer_id!r} not found"
            )
        # Lock the stock rows in ascending store-id order, the same order
        # used by create_transfer, so concurrent operations never acquire
        # the same locks in opposite order.
        store_ids = sorted(
            store_id
            for store_id in (transfer.src_store_id, transfer.dest_store_id)
            if store_id is not None
        )
        stocks = {}
        for store_id in store_ids:
            stock = await self.stock_repo.lock_stock(connection, transfer.item_id, store_id)
            if stock is None:
                raise TransferError(404, f"stock with id {store_id!r} not found")
            stocks[store_id] = stock
        if transfer.src_store_id is not None:
            transfer.src_stock = stocks[transfer.src_store_id]
        if transfer.dest_store_id is not None:
            transfer.dest_stock = stocks[transfer.dest_store_id]

        return transfer

    async def _save_transfer_with_stock(self, connection: asyncpg.Connection, transfer) -> None:
        await self.transfers_repo.update_transfer(connection, transfer)
        if transfer.src_stock is not None:
            await self.stock_repo.update_stock(connection, transfer.src_stock)
        if transfer.dest_stock is not None:
            await self.stock_repo.update_stock(connection, transfer.dest_stock)
