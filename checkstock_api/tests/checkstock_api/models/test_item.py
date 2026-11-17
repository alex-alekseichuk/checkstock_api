"""Tests for the Item model (stock.items)."""

from datetime import datetime
from uuid import UUID

from checkstock_api.models.item import Item
from tests.checkstock_api.models.fakerecord import FakeRow


def test_item_from_row_maps_all_fields() -> None:
    item_id = UUID("11111111-1111-1111-1111-111111111111")
    created_at = datetime(2026, 1, 2, 3, 4, 5)
    row = FakeRow(id=item_id, sku="SKU-1", title="Widget", created_at=created_at)

    item = Item.from_row(row)

    assert item.id == item_id
    assert item.sku == "SKU-1"
    assert item.title == "Widget"
    assert item.created_at == created_at


def test_item_direct_construction() -> None:
    item = Item(
        id=UUID(int=1),
        sku="SKU-2",
        title="Gadget",
        created_at=datetime(2026, 2, 3),
    )

    assert item.id == UUID(int=1)
    assert item.sku == "SKU-2"
    assert item.title == "Gadget"
    assert item.created_at == datetime(2026, 2, 3)
