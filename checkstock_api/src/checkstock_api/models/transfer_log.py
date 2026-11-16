"""Transfer log model, matching the ``stock.transfer_logs`` table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from asyncpg import Record

from checkstock_api.models.transfer import TransferEvent


@dataclass(frozen=True)
class TransferLog:
    """One state-change event in a transfer's lifecycle (one row per event)."""

    id: int
    transfer_id: UUID
    event: TransferEvent
    logged_at: datetime

    @classmethod
    def from_row(cls, row: "Record") -> "TransferLog":
        """Build a ``TransferLog`` from a single row of ``SELECT ... FROM stock.transfer_logs``."""
        return cls(
            id=row["id"],
            transfer_id=row["transfer_id"],
            event=TransferEvent(row["event"]),
            logged_at=row["logged_at"],
        )
