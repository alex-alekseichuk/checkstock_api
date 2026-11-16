"""Transfer model, matching the ``stock.transfers`` table."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from checkstock_api.models import Stock

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


initial_status = {
    TransferType.INBOUND: TransferStatus.RECEIVED,
    TransferType.TRANSFER: TransferStatus.IN_TRANSIT,
    TransferType.SHIP_FBO: TransferStatus.IN_TRANSIT,
    TransferType.SHIP_FBS: TransferStatus.RESERVED,
}


initial_event = {
    TransferType.INBOUND: TransferEvent.RECEIVED,
    TransferType.TRANSFER: TransferEvent.SENT,
    TransferType.SHIP_FBO: TransferEvent.SENT,
    TransferType.SHIP_FBS: TransferEvent.RESERVED,
}


class TransferError(Exception):
    """Domain error while creating a transfer.

    Carries the HTTP ``status_code`` the route should answer with and the
    human-readable ``detail``.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


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
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

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

    @classmethod
    def create(cls, type, item_id, quantity, src_stock, dest_stock, id):
        """Check data, create the transfer object and return it."""

        status = initial_status.get(type, None)
        if status is None:
            raise TransferError(400, f"Unknown transfer type {type}")

        if (src_stock is None and (type == TransferType.TRANSFER or type == TransferType.SHIP_FBO or type == TransferType.SHIP_FBS)):
            raise TransferError(400, f"Source store is required for type {type}")
        if dest_stock is None and (type == TransferType.INBOUND or type == TransferType.TRANSFER):
            raise TransferError(400, f"Destination store is required for type {type}")

        if (type == TransferType.TRANSFER or type == TransferType.SHIP_FBO or type == TransferType.SHIP_FBS) and src_stock.quantity - src_stock.reserved < quantity:
            raise TransferError(409, f"Source store has no enough quantity of item_id {item_id}")

        if type == TransferType.TRANSFER or type == TransferType.SHIP_FBO:
            src_stock.quantity -= quantity
        if type == TransferType.SHIP_FBS:
            src_stock.reserved += quantity

        return (
            initial_event.get(type, None),
            cls(
                id=id,
                item_id=item_id,
                quantity=quantity,
                type=type,
                src_stock_id=src_stock.store_id if src_stock else None,
                dest_stock_id=dest_stock.store_id if dest_stock else None,
                status=status
            )
        )
