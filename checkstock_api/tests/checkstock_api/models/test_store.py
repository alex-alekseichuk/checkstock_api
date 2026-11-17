"""Tests for the Store model (stock.stores)."""

from datetime import datetime
from uuid import UUID

import pytest

from checkstock_api.models.store import Store, StoreError, StoreStatus
from tests.checkstock_api.models.fakerecord import FakeRow


def test_store_status_values() -> None:
    assert StoreStatus.ACTIVE.value == "active"
    assert StoreStatus.CLOSED.value == "closed"
    assert StoreStatus("active") is StoreStatus.ACTIVE
    assert StoreStatus("closed") is StoreStatus.CLOSED


def test_store_from_row_maps_all_fields() -> None:
    store_id = UUID("22222222-2222-2222-2222-222222222222")
    created_at = datetime(2026, 1, 2, 3, 4, 5)
    row = FakeRow(id=store_id, title="Minsk FF", status="active", created_at=created_at)

    store = Store.from_row(row)

    assert store.id == store_id
    assert store.title == "Minsk FF"
    assert store.status is StoreStatus.ACTIVE
    assert store.created_at == created_at


def test_store_from_row_parses_closed_status() -> None:
    row = FakeRow(id=UUID(int=1), title="FF 2", status="closed", created_at=datetime(2026, 1, 1))

    assert Store.from_row(row).status is StoreStatus.CLOSED


def test_store_from_row_rejects_unknown_status() -> None:
    row = FakeRow(id=UUID(int=1), title="FF 2", status="bogus", created_at=datetime(2026, 1, 1))

    with pytest.raises(ValueError):
        Store.from_row(row)


def test_store_error_carries_status_code_and_detail() -> None:
    error = StoreError(404, "store not found")

    assert error.status_code == 404
    assert error.detail == "store not found"
    assert str(error) == "store not found"
