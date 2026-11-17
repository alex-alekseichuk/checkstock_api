"""Tests for the Stock model (stock.stock)."""

from datetime import datetime
from uuid import UUID

from checkstock_api.models.stock import Stock
from tests.checkstock_api.models.fakerecord import FakeRow


def test_stock_from_row_maps_all_fields() -> None:
    item_id = UUID("11111111-1111-1111-1111-111111111111")
    store_id = UUID("22222222-2222-2222-2222-222222222222")
    created_at = datetime(2026, 1, 2, 3, 4, 5)
    row = FakeRow(item_id=item_id, store_id=store_id, quantity=10, reserved=2, created_at=created_at)

    stock = Stock.from_row(row)

    assert stock.item_id == item_id
    assert stock.store_id == store_id
    assert stock.quantity == 10
    assert stock.reserved == 2
    assert stock.created_at == created_at


def test_stock_is_mutable() -> None:
    stock = Stock(
        item_id=UUID(int=1),
        store_id=UUID(int=2),
        quantity=5,
        reserved=1,
        created_at=datetime(2026, 1, 1),
    )
    stock.quantity -= 2

    assert stock.quantity == 3
    assert stock.reserved == 1
