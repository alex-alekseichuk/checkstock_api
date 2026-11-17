"""Store (fulfillment center / FF store) model, matching ``stock.stores``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from asyncpg import Record


class StoreStatus(str, Enum):
    """Value of the ``stock.store_status`` enum."""

    ACTIVE = "active"
    CLOSED = "closed"


class StoreError(Exception):
    """Domain error while processing a store.

    Carries the HTTP ``status_code`` the route should answer with and the
    human-readable ``detail``.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class Store:
    """A fulfillment center (FF store) holding stock for items."""

    id: UUID
    title: str
    status: StoreStatus
    created_at: datetime

    @classmethod
    def from_row(cls, row: "Record") -> "Store":
        """Build a ``Store`` from a single row of ``SELECT ... FROM stock.stores``."""
        return cls(
            id=row["id"],
            title=row["title"],
            status=StoreStatus(row["status"]),
            created_at=row["created_at"],
        )
