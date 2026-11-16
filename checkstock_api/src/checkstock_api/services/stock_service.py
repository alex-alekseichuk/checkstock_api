"""Service layer for on-hand stock, on top of ``StockRepo``."""

from __future__ import annotations

from asyncpg import Record

from checkstock_api.models.transfer import TransferType
from checkstock_api.repositories.stock_repo import StockRepo


class StockService:
    """Business operations for on-hand stock."""

    def __init__(self, stock_repo: StockRepo) -> None:
        self.stock_repo = stock_repo

    async def list_stock(self) -> list[Record]:
        """List stock with ``quantity > 0`` at active stores."""
        return await self.stock_repo.list_stock()

    async def list_in_transit(
        self, transfer_type: TransferType | None = None
    ) -> list[Record]:
        """List in-transit transfers, optionally filtered by ``transfer_type``."""
        return await self.stock_repo.list_in_transit(transfer_type)
