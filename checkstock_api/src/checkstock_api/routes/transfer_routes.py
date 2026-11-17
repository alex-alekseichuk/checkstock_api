"""HTTP routes for transfers."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from checkstock_api.models.transfer import Transfer, TransferType
from checkstock_api.services.transfer_service import TransferError, TransferService


class TransferCreate(BaseModel):
    """Payload for ``POST /transfers/``.

    ``type`` selects the movement kind and which stores are required:
    ``inbound`` (destination only), ``transfer`` (source and destination),
    ``ship_fbo`` / ``ship_fbs`` (source only).
    """

    type: TransferType
    source_store_id: UUID | None = Field(
        None, description="FF store the goods leave from"
    )
    dest_store_id: UUID | None = Field(
        None, description="FF store the goods arrive to"
    )
    sku: str
    quantity: int = Field(gt=0, description="Units to move")


def create_transfers_router(transfers_service: TransferService) -> APIRouter:
    """Build the transfers router bound to the given service."""
    router = APIRouter(prefix="/transfers", tags=["transfers"])

    @router.post("/", status_code=status.HTTP_201_CREATED, response_model=Transfer)
    async def create_transfer(payload: TransferCreate) -> Transfer:
        """Create a new transfer and apply its stock effects atomically."""
        try:
            return await transfers_service.create_transfer(
                type=payload.type,
                sku=payload.sku,
                quantity=payload.quantity,
                source_store_id=payload.source_store_id,
                dest_store_id=payload.dest_store_id,
            )
        except TransferError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.post("/{transfer_id}/receive", response_model=Transfer)
    async def receive_transfer(transfer_id: UUID) -> Transfer:
        """Receive an in-transit transfer: the goods arrive at the
        destination store and the transfer reaches ``received`` state."""
        try:
            return await transfers_service.receive_transfer(transfer_id)
        except TransferError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.post("/{transfer_id}/cancel", response_model=Transfer)
    async def cancel_transfer(transfer_id: UUID) -> Transfer:
        """Cancel a reserved FBS shipment: the reservation of the source
        store's stock is released and the transfer reaches ``canceled``
        state."""
        try:
            return await transfers_service.cancel_transfer(transfer_id)
        except TransferError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.post("/{transfer_id}/approve", response_model=Transfer)
    async def approve_transfer(transfer_id: UUID) -> Transfer:
        """Approve a reserved FBS shipment: the reserved goods leave the
        source store and the transfer goes into transit."""
        try:
            return await transfers_service.approve_transfer(transfer_id)
        except TransferError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return router
