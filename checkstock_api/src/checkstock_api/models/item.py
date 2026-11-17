"""Item (product / SKU) model, matching the ``stock.items`` table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from asyncpg import Record


@dataclass
class Item:
    """A product (артикул) stocked at one or more FF stores."""

    id: UUID
    sku: str
    title: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: "Record") -> "Item":
        """Build an ``Item`` from a single row of ``SELECT ... FROM stock.items``."""
        return cls(
            id=row["id"],
            sku=row["sku"],
            title=row["title"],
            created_at=row["created_at"],
        )
