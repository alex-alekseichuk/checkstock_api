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
    SHIPPED = "shipped"
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
    TransferType.TRANSFER: TransferEvent.SHIPPED,
    TransferType.SHIP_FBO: TransferEvent.SHIPPED,
    TransferType.SHIP_FBS: TransferEvent.RESERVED,
}


class TransferError(Exception):
    """Domain error while processing a transfer.

    Carries the HTTP ``status_code`` the route should answer with and the
    human-readable ``detail``.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class Transfer:
    """A stock movement: inbound receipt, inter-FF transfer, or FBO / FBS shipment.

    ``src_store_id`` / ``dest_store_id`` are the source and destination FF
    stores; either is ``None`` when the movement has no FF store on that side.
    """

    id: UUID
    item_id: UUID
    quantity: int
    type: TransferType
    src_store_id: UUID | None
    dest_store_id: UUID | None
    src_stock: Stock | None
    dest_stock: Stock | None
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
            src_store_id=row["src_store_id"],
            dest_store_id=row["dest_store_id"],
            src_stock=None,
            dest_stock=None,
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
        if type == TransferType.INBOUND:
            dest_stock.quantity += quantity

        return (
            initial_event.get(type, None),
            cls(
                id=id,
                item_id=item_id,
                quantity=quantity,
                type=type,
                src_store_id=src_stock.store_id if src_stock else None,
                dest_store_id=dest_stock.store_id if dest_stock else None,
                src_stock=src_stock,
                dest_stock=dest_stock,
                status=status
            )
        )

    def receive(self):
        if not (self.type == TransferType.TRANSFER or self.type == TransferType.SHIP_FBO or self.type == TransferType.SHIP_FBS):
            return None

        if self.status != TransferStatus.IN_TRANSIT:
            return None

        if self.type == TransferType.TRANSFER:
            if self.dest_stock is None:
                return None
            self.dest_stock.quantity += self.quantity

        self.status = TransferStatus.RECEIVED

        return TransferEvent.RECEIVED

    def cancel(self):
        if not (self.type == TransferType.SHIP_FBS and self.status == TransferStatus.RESERVED):
            return None
        if self.src_stock is None:
            return None
        if self.src_stock.reserved < self.quantity:
            return None

        self.src_stock.reserved -= self.quantity
        self.status = TransferStatus.CANCELED

        return TransferEvent.CANCELED

    def approve(self):
        if not (self.type == TransferType.SHIP_FBS and self.status == TransferStatus.RESERVED):
            return None
        if self.src_stock is None:
            return None
        if self.src_stock.reserved < self.quantity or self.src_stock.quantity < self.quantity:
            return None

        self.src_stock.reserved -= self.quantity
        self.src_stock.quantity -= self.quantity
        self.status = TransferStatus.IN_TRANSIT

        return TransferEvent.SHIPPED
