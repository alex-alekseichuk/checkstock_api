"""Transfer model, matching the ``stock.transfers`` table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from asyncpg import Record


class TransferType(str, Enum):
    """Value of the ``stock.transfer_type`` enum."""

    INBOUND = "inbound"
    TRANSFER = "transfer"
    SHIP_FBO = "ship_fbo"
    SHIP_FBS = "ship_fbs"


class TransferStatus(str, Enum):
    """Value of the ``stock.transfer_status`` enum."""

    RESERVED = "reserved"
    CANCELED = "canceled"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"


class TransferEvent(str, Enum):
    """Value of the ``stock.transfer_event`` enum (see ``TransferLog``)."""

    INBOUND = "inbound"
    SENT = "sent"
    RECEIVED = "received"
    RESERVED = "reserved"
    CANCELED = "canceled"


@dataclass(frozen=True)
class Transfer:
    """A stock movement: inbound receipt, inter-FF transfer, or FBO / FBS shipment.

    ``src_stock_id`` / ``dest_stock_id`` are the source and destination FF
    stores; either is ``None`` when the movement has no FF store on that side.
    """

    id: UUID
    item_id: UUID
    quantity: int
    type: TransferType
    src_stock_id: UUID | None
    dest_stock_id: UUID | None
    status: TransferStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: "Record") -> "Transfer":
        """Build a ``Transfer`` from a single row of ``SELECT ... FROM stock.transfers``."""
        return cls(
            id=row["id"],
            item_id=row["item_id"],
            quantity=row["quantity"],
            type=TransferType(row["type"]),
            src_stock_id=row["src_stock_id"],
            dest_stock_id=row["dest_stock_id"],
            status=TransferStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
