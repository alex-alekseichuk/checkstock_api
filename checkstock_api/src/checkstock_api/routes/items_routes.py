"""HTTP routes for items."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel

from checkstock_api.models.item import Item
from checkstock_api.services.items_service import ItemsService


class ItemCreate(BaseModel):
    """Payload for ``POST /items/``."""

    sku: str
    title: str


def create_items_router(items_service: ItemsService) -> APIRouter:
    """Build the items router bound to the given service."""
    router = APIRouter(prefix="/items", tags=["items"])

    @router.post("/", status_code=status.HTTP_201_CREATED, response_model=Item)
    async def create_item(payload: ItemCreate) -> Item:
        """Create a new item."""
        return await items_service.add_item(payload.sku, payload.title)

    return router
