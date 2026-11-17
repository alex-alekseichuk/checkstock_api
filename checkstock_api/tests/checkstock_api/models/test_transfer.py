"""Tests for the Transfer model (stock.transfers)."""

from datetime import datetime
from uuid import UUID

import pytest

from checkstock_api.models.stock import Stock
from checkstock_api.models.transfer import (
    Transfer,
    TransferError,
    TransferEvent,
    TransferStatus,
    TransferType,
    initial_event,
    initial_status,
)
from tests.checkstock_api.models.fakerecord import FakeRow


def make_stock(quantity: int, reserved: int, store_id: UUID | None = None) -> Stock:
    """Build a standalone ``Stock`` for use as a transfer endpoint."""
    return Stock(
        item_id=UUID(int=1),
        store_id=store_id or UUID(int=2),
        quantity=quantity,
        reserved=reserved,
        created_at=datetime(2026, 1, 1),
    )


def make_transfer(
    transfer_type: TransferType,
    status: TransferStatus,
    quantity: int = 1,
    src_stock: Stock | None = None,
    dest_stock: Stock | None = None,
) -> Transfer:
    """Build a ``Transfer`` directly, bypassing ``create``."""
    return Transfer(
        id=UUID(int=1),
        item_id=UUID(int=2),
        quantity=quantity,
        type=transfer_type,
        src_store_id=src_stock.store_id if src_stock else None,
        dest_store_id=dest_stock.store_id if dest_stock else None,
        src_stock=src_stock,
        dest_stock=dest_stock,
        status=status,
    )


# --- enums and mapping tables -------------------------------------------------


def test_transfer_type_values() -> None:
    assert {t.value for t in TransferType} == {"inbound", "transfer", "ship_fbo", "ship_fbs"}


def test_transfer_status_values() -> None:
    assert {s.value for s in TransferStatus} == {"reserved", "canceled", "in_transit", "received"}


def test_transfer_event_values() -> None:
    assert {e.value for e in TransferEvent} == {"inbound", "shipped", "received", "reserved", "canceled"}


def test_initial_status_mapping() -> None:
    assert initial_status == {
        TransferType.INBOUND: TransferStatus.RECEIVED,
        TransferType.TRANSFER: TransferStatus.IN_TRANSIT,
        TransferType.SHIP_FBO: TransferStatus.IN_TRANSIT,
        TransferType.SHIP_FBS: TransferStatus.RESERVED,
    }


def test_initial_event_mapping() -> None:
    assert initial_event == {
        TransferType.INBOUND: TransferEvent.RECEIVED,
        TransferType.TRANSFER: TransferEvent.SHIPPED,
        TransferType.SHIP_FBO: TransferEvent.SHIPPED,
        TransferType.SHIP_FBS: TransferEvent.RESERVED,
    }


def test_transfer_error_carries_status_code_and_detail() -> None:
    error = TransferError(409, "not enough stock")

    assert isinstance(error, Exception)
    assert error.status_code == 409
    assert error.detail == "not enough stock"
    assert str(error) == "not enough stock"


# --- from_row -----------------------------------------------------------------


def test_transfer_from_row_maps_all_fields() -> None:
    now = datetime(2026, 4, 5, 6, 7, 8)
    row = FakeRow(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        item_id=UUID("11111111-1111-1111-1111-111111111111"),
        quantity=5,
        type="transfer",
        src_store_id=UUID("22222222-2222-2222-2222-222222222222"),
        dest_store_id=UUID("55555555-5555-5555-5555-555555555555"),
        status="in_transit",
        created_at=now,
        updated_at=now,
    )

    transfer = Transfer.from_row(row)

    assert transfer.id == UUID("44444444-4444-4444-4444-444444444444")
    assert transfer.item_id == UUID("11111111-1111-1111-1111-111111111111")
    assert transfer.quantity == 5
    assert transfer.type is TransferType.TRANSFER
    assert transfer.src_store_id == UUID("22222222-2222-2222-2222-222222222222")
    assert transfer.dest_store_id == UUID("55555555-5555-5555-5555-555555555555")
    assert transfer.src_stock is None
    assert transfer.dest_stock is None
    assert transfer.status is TransferStatus.IN_TRANSIT
    assert transfer.created_at == now
    assert transfer.updated_at == now


def test_transfer_timestamp_defaults_are_set() -> None:
    before = datetime.now()

    transfer = make_transfer(TransferType.INBOUND, TransferStatus.RECEIVED)

    assert transfer.created_at >= before
    assert transfer.updated_at >= before


# --- create -------------------------------------------------------------------


def test_create_inbound_increases_dest_quantity() -> None:
    dest = make_stock(quantity=1, reserved=0, store_id=UUID(int=10))

    event, transfer = Transfer.create(TransferType.INBOUND, UUID(int=1), 5, None, dest, UUID(int=100))

    assert event is TransferEvent.RECEIVED
    assert transfer.status is TransferStatus.RECEIVED
    assert transfer.type is TransferType.INBOUND
    assert transfer.src_store_id is None
    assert transfer.dest_store_id == dest.store_id
    assert dest.quantity == 6
    assert dest.reserved == 0


def test_create_inbound_requires_dest() -> None:
    with pytest.raises(TransferError) as exc:
        Transfer.create(TransferType.INBOUND, UUID(int=1), 5, None, None, UUID(int=100))

    assert exc.value.status_code == 400
    assert "Destination store is required" in exc.value.detail


def test_create_transfer_decreases_src_quantity() -> None:
    src = make_stock(quantity=10, reserved=2)
    dest = make_stock(quantity=0, reserved=0, store_id=UUID(int=10))

    event, transfer = Transfer.create(TransferType.TRANSFER, UUID(int=1), 3, src, dest, UUID(int=100))

    assert event is TransferEvent.SHIPPED
    assert transfer.status is TransferStatus.IN_TRANSIT
    assert transfer.src_store_id == src.store_id
    assert transfer.dest_store_id == dest.store_id
    assert src.quantity == 7
    assert src.reserved == 2


def test_create_transfer_requires_src_and_dest() -> None:
    dest = make_stock(quantity=0, reserved=0, store_id=UUID(int=10))
    with pytest.raises(TransferError) as exc:
        Transfer.create(TransferType.TRANSFER, UUID(int=1), 3, None, dest, UUID(int=100))
    assert exc.value.status_code == 400
    assert "Source store is required" in exc.value.detail

    src = make_stock(quantity=10, reserved=0)
    with pytest.raises(TransferError) as exc:
        Transfer.create(TransferType.TRANSFER, UUID(int=1), 3, src, None, UUID(int=100))
    assert exc.value.status_code == 400
    assert "Destination store is required" in exc.value.detail


def test_create_transfer_rejects_quantity_above_available() -> None:
    src = make_stock(quantity=10, reserved=4)  # only 6 available
    dest = make_stock(quantity=0, reserved=0, store_id=UUID(int=10))

    with pytest.raises(TransferError) as exc:
        Transfer.create(TransferType.TRANSFER, UUID(int=1), 7, src, dest, UUID(int=100))

    assert exc.value.status_code == 409
    assert "no enough quantity" in exc.value.detail
    assert src.quantity == 10  # nothing mutated on failure


def test_create_transfer_allows_exactly_available() -> None:
    src = make_stock(quantity=10, reserved=4)  # exactly 6 available
    dest = make_stock(quantity=0, reserved=0, store_id=UUID(int=10))

    event, _ = Transfer.create(TransferType.TRANSFER, UUID(int=1), 6, src, dest, UUID(int=100))

    assert event is TransferEvent.SHIPPED
    assert src.quantity == 4


def test_create_ship_fbo_decreases_src_without_dest() -> None:
    src = make_stock(quantity=10, reserved=2)

    event, transfer = Transfer.create(TransferType.SHIP_FBO, UUID(int=1), 4, src, None, UUID(int=100))

    assert event is TransferEvent.SHIPPED
    assert transfer.status is TransferStatus.IN_TRANSIT
    assert transfer.src_store_id == src.store_id
    assert transfer.dest_store_id is None
    assert src.quantity == 6
    assert src.reserved == 2


def test_create_ship_fbo_rejects_quantity_above_available() -> None:
    src = make_stock(quantity=5, reserved=4)  # only 1 available

    with pytest.raises(TransferError) as exc:
        Transfer.create(TransferType.SHIP_FBO, UUID(int=1), 2, src, None, UUID(int=100))

    assert exc.value.status_code == 409


def test_create_ship_fbo_requires_src() -> None:
    with pytest.raises(TransferError) as exc:
        Transfer.create(TransferType.SHIP_FBO, UUID(int=1), 1, None, None, UUID(int=100))

    assert exc.value.status_code == 400
    assert "Source store is required" in exc.value.detail


def test_create_ship_fbs_increases_reserved() -> None:
    src = make_stock(quantity=10, reserved=2)

    event, transfer = Transfer.create(TransferType.SHIP_FBS, UUID(int=1), 4, src, None, UUID(int=100))

    assert event is TransferEvent.RESERVED
    assert transfer.status is TransferStatus.RESERVED
    assert transfer.src_store_id == src.store_id
    assert transfer.dest_store_id is None
    assert src.quantity == 10
    assert src.reserved == 6


def test_create_ship_fbs_rejects_quantity_above_available() -> None:
    src = make_stock(quantity=10, reserved=6)  # only 4 available

    with pytest.raises(TransferError) as exc:
        Transfer.create(TransferType.SHIP_FBS, UUID(int=1), 5, src, None, UUID(int=100))

    assert exc.value.status_code == 409
    assert src.reserved == 6  # nothing mutated on failure


def test_create_ship_fbs_requires_src() -> None:
    with pytest.raises(TransferError) as exc:
        Transfer.create(TransferType.SHIP_FBS, UUID(int=1), 1, None, None, UUID(int=100))

    assert exc.value.status_code == 400
    assert "Source store is required" in exc.value.detail


def test_create_unknown_type_is_rejected() -> None:
    with pytest.raises(TransferError) as exc:
        Transfer.create("mystery", UUID(int=1), 1, None, None, UUID(int=100))

    assert exc.value.status_code == 400
    assert "Unknown transfer type" in exc.value.detail


# --- receive ------------------------------------------------------------------


def test_receive_transfer_adds_to_dest() -> None:
    src = make_stock(quantity=10, reserved=0)
    dest = make_stock(quantity=0, reserved=0, store_id=UUID(int=10))
    _, transfer = Transfer.create(TransferType.TRANSFER, UUID(int=1), 3, src, dest, UUID(int=100))

    assert transfer.receive() is TransferEvent.RECEIVED
    assert transfer.status is TransferStatus.RECEIVED
    assert dest.quantity == 3


def test_receive_is_noop_when_not_in_transit() -> None:
    transfer = make_transfer(TransferType.TRANSFER, TransferStatus.RESERVED, quantity=3)

    assert transfer.receive() is None
    assert transfer.status is TransferStatus.RESERVED


def test_receive_transfer_without_dest_is_noop() -> None:
    transfer = make_transfer(TransferType.TRANSFER, TransferStatus.IN_TRANSIT, quantity=3)

    assert transfer.receive() is None
    assert transfer.status is TransferStatus.IN_TRANSIT


def test_receive_inbound_is_noop() -> None:
    transfer = make_transfer(TransferType.INBOUND, TransferStatus.RECEIVED, quantity=3)

    assert transfer.receive() is None
    assert transfer.status is TransferStatus.RECEIVED


def test_receive_ship_fbo() -> None:
    src = make_stock(quantity=10, reserved=0)
    _, transfer = Transfer.create(TransferType.SHIP_FBO, UUID(int=1), 3, src, None, UUID(int=100))

    assert transfer.receive() is TransferEvent.RECEIVED
    assert transfer.status is TransferStatus.RECEIVED


def test_receive_ship_fbs_after_approve() -> None:
    src = make_stock(quantity=10, reserved=6)
    _, transfer = Transfer.create(TransferType.SHIP_FBS, UUID(int=1), 4, src, None, UUID(int=100))

    assert src.reserved == 10  # reservation applied by create
    assert transfer.receive() is None  # still RESERVED
    assert transfer.approve() is TransferEvent.SHIPPED
    assert transfer.receive() is TransferEvent.RECEIVED
    assert transfer.status is TransferStatus.RECEIVED
    assert src.reserved == 6
    assert src.quantity == 6


# --- cancel -------------------------------------------------------------------


def test_cancel_ship_fbs_restores_reserved() -> None:
    src = make_stock(quantity=10, reserved=6)
    _, transfer = Transfer.create(TransferType.SHIP_FBS, UUID(int=1), 4, src, None, UUID(int=100))

    assert src.reserved == 10  # reservation applied by create
    assert transfer.cancel() is TransferEvent.CANCELED
    assert transfer.status is TransferStatus.CANCELED
    assert src.reserved == 6
    assert src.quantity == 10


def test_cancel_fails_when_reserved_too_low() -> None:
    transfer = make_transfer(TransferType.SHIP_FBS, TransferStatus.RESERVED, quantity=5, src_stock=make_stock(quantity=10, reserved=4))

    assert transfer.cancel() is None
    assert transfer.status is TransferStatus.RESERVED
    assert transfer.src_stock.reserved == 4


def test_cancel_fails_without_src_stock() -> None:
    transfer = make_transfer(TransferType.SHIP_FBS, TransferStatus.RESERVED, quantity=5)

    assert transfer.cancel() is None
    assert transfer.status is TransferStatus.RESERVED


def test_cancel_is_noop_for_other_types_and_statuses() -> None:
    transfer = make_transfer(TransferType.TRANSFER, TransferStatus.IN_TRANSIT)

    assert transfer.cancel() is None
    assert transfer.status is TransferStatus.IN_TRANSIT

    shipped = make_transfer(TransferType.SHIP_FBS, TransferStatus.IN_TRANSIT, quantity=5, src_stock=make_stock(quantity=10, reserved=4))

    assert shipped.cancel() is None
    assert shipped.status is TransferStatus.IN_TRANSIT


# --- approve ------------------------------------------------------------------


def test_approve_ship_fbs_ships() -> None:
    src = make_stock(quantity=10, reserved=6)
    _, transfer = Transfer.create(TransferType.SHIP_FBS, UUID(int=1), 4, src, None, UUID(int=100))

    assert src.reserved == 10  # reservation applied by create
    assert transfer.approve() is TransferEvent.SHIPPED
    assert transfer.status is TransferStatus.IN_TRANSIT
    assert src.reserved == 6
    assert src.quantity == 6


def test_approve_fails_when_reserved_too_low() -> None:
    src = make_stock(quantity=10, reserved=4)
    transfer = make_transfer(TransferType.SHIP_FBS, TransferStatus.RESERVED, quantity=5, src_stock=src)

    assert transfer.approve() is None
    assert transfer.status is TransferStatus.RESERVED
    assert src.reserved == 4
    assert src.quantity == 10


def test_approve_fails_when_quantity_too_low() -> None:
    src = make_stock(quantity=3, reserved=3)
    transfer = make_transfer(TransferType.SHIP_FBS, TransferStatus.RESERVED, quantity=5, src_stock=src)

    assert transfer.approve() is None
    assert transfer.status is TransferStatus.RESERVED
    assert src.reserved == 3
    assert src.quantity == 3


def test_approve_fails_without_src_stock() -> None:
    transfer = make_transfer(TransferType.SHIP_FBS, TransferStatus.RESERVED, quantity=5)

    assert transfer.approve() is None
    assert transfer.status is TransferStatus.RESERVED


def test_approve_is_noop_for_other_types_and_statuses() -> None:
    transfer = make_transfer(TransferType.TRANSFER, TransferStatus.IN_TRANSIT, quantity=1, src_stock=make_stock(quantity=10, reserved=0))

    assert transfer.approve() is None
    assert transfer.status is TransferStatus.IN_TRANSIT
