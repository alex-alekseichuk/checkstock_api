"""On-hand stock model, matching the ``stock.stock`` table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from asyncpg import Record


@dataclass(frozen=True)
class Stock:
    """On-hand stock of an item at one FF store.

    Composite primary key ``(item_id, stock_id)``; ``reserved`` is the part of
    ``quantity`` blocked for orders (``quantity >= reserved``).
    """

    item_id: UUID
    stock_id: UUID
    quantity: int
    reserved: int
    created_at: datetime

    @classmethod
    def from_row(cls, row: "Record") -> "Stock":
        """Build a ``Stock`` from a single row of ``SELECT ... FROM stock.stock``."""
        return cls(
            item_id=row["item_id"],
            stock_id=row["stock_id"],
            quantity=row["quantity"],
            reserved=row["reserved"],
            created_at=row["created_at"],
        )
