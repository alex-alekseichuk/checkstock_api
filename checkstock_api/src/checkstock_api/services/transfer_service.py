"""Service layer for transfers, on top of the item/store/stock/transfer repos.

Creating a transfer is a unit of work: the type is validated against the
given stores, the stores are checked to exist and be active, the source
store's available quantity is checked, and the transfer record, its stock
effects and its first event log are written inside one transaction.
"""

from __future__ import annotations

from uuid import UUID

from checkstock_api.common.db import Database
from checkstock_api.models.transfer import Transfer, TransferType, TransferError
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
            item = await self.items_repo.get_by_sku(sku)
            if item is None:
                raise TransferError(404, f"item with sku {sku!r} not found")

            src_stock = None
            if source_store_id is not None:
                source_store = await self.stores_repo.get(source_store_id)
                if source_store is None:
                    raise TransferError(404, f"store with id {source_store_id!r} not found")
                src_stock = await self.stock_repo.lock_stock(
                    connection, item.id, source_store.id
                )

            dest_stock = None
            if dest_store_id is not None:
                dest_store = await self.stores_repo.get(dest_store_id)
                if dest_store is None:
                    raise TransferError(404, f"store with id {dest_store_id!r} not found")
                dest_stock = await self.stock_repo.lock_stock(
                    connection, item.id, dest_store.id
                )
                if (type == TransferType.INBOUND or type == TransferType.TRANSFER) and dest_stock is None:
                    dest_stock = await self.stock_repo.create_lock_stock(connection, item.id, dest_store.id)

            event, transfer = Transfer.create(
                type=type,
                item_id=item.id,
                quantity=quantity,
                src_stock=src_stock,
                dest_stock=dest_stock,
                id=id
            )

            transfer = await self.transfers_repo.insert_transfer(
                connection,
                transfer
            )

            if (type == TransferType.TRANSFER or type == TransferType.SHIP_FBO or type == TransferType.SHIP_FBS) and (src_stock is not None):
                await self.stock_repo.save_stock(connection, src_stock)

            if (type == TransferType.INBOUND) and (dest_stock is not None):
                await self.stock_repo.save_stock(connection, dest_stock)

            await self.transfers_repo.insert_log(connection, transfer.id, event)

            return transfer
