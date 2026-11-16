"""HTTP routes for on-hand stock and in-transit transfers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from checkstock_api.models.transfer import TransferType
from checkstock_api.services.stock_service import StockService

# Transfer types that can be in transit (``inbound`` excluded).
InTransitType = Literal["transfer", "ship_fbo", "ship_fbs"]


class StockEntry(BaseModel):
    """A stock row: item + store + quantities."""

    item_id: UUID
    item_sku: str
    item_title: str
    store_id: UUID
    store_title: str
    quantity: int
    reserved: int
    available: int


class InTransitEntry(BaseModel):
    """An in-transit transfer row: item + source/destination stores."""

    item_id: UUID
    item_sku: str
    item_title: str
    source_store_id: UUID | None
    source_store_title: str | None
    dest_store_id: UUID | None
    dest_store_title: str | None
    quantity: int
    type: TransferType
    departed_at: datetime


def create_stock_router(stock_service: StockService) -> APIRouter:
    """Build the stock router bound to the given service."""
    router = APIRouter(prefix="/stock", tags=["stock"])

    @router.get("/", response_model=list[StockEntry])
    async def list_stock() -> list[StockEntry]:
        """List on-hand stock (``quantity > 0``) at active stores."""
        rows = await stock_service.list_stock()
        return [StockEntry.model_validate(dict(row)) for row in rows]

    @router.get("/in_transit", response_model=list[InTransitEntry])
    async def list_in_transit(
        type: InTransitType | None = Query(
            None,
            description="Filter by transfer type: ``transfer``, "
            "``ship_fbo`` or ``ship_fbs``. Omit to list all.",
        ),
    ) -> list[InTransitEntry]:
        """List in-transit transfers, optionally filtered by ``type``."""
        rows = await stock_service.list_in_transit(
            TransferType(type) if type is not None else None
        )
        return [InTransitEntry.model_validate(dict(row)) for row in rows]

    return router
