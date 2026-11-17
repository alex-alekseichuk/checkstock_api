"""HTTP routes for stores."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from checkstock_api.models.store import Store, StoreError, StoreStatus
from checkstock_api.services.stores_service import StoresService


class StoreCreate(BaseModel):
    """Payload for ``POST /stores/``."""

    title: str
    status: StoreStatus = StoreStatus.ACTIVE


def create_stores_router(stores_service: StoresService) -> APIRouter:
    """Build the stores router bound to the given service."""
    router = APIRouter(prefix="/stores", tags=["stores"])

    @router.post("/", status_code=status.HTTP_201_CREATED, response_model=Store)
    async def create_store(payload: StoreCreate) -> Store:
        """Create a new store."""
        return await stores_service.add_store(payload.title, payload.status)

    @router.delete("/{store_id}/", response_model=Store)
    async def close_store(store_id: UUID) -> Store:
        """Close a store (set its status to ``closed``).

        Returns the updated store; 404 when no store with ``store_id``
        exists, 409 when the store is not empty.
        """
        try:
            return await stores_service.close_store(store_id)
        except StoreError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return router
