"""Tests for the TransferLog model (stock.transfer_logs)."""

from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import UUID

import pytest

from checkstock_api.models.transfer import TransferEvent
from checkstock_api.models.transfer_log import TransferLog
from tests.checkstock_api.models.fakerecord import FakeRow


def test_transfer_log_from_row_maps_all_fields() -> None:
    transfer_id = UUID("33333333-3333-3333-3333-333333333333")
    logged_at = datetime(2026, 1, 2, 3, 4, 5)
    row = FakeRow(id=7, transfer_id=transfer_id, event="shipped", logged_at=logged_at)

    log = TransferLog.from_row(row)

    assert log.id == 7
    assert log.transfer_id == transfer_id
    assert log.event is TransferEvent.SHIPPED
    assert log.logged_at == logged_at


def test_transfer_log_is_frozen() -> None:
    log = TransferLog(
        id=1,
        transfer_id=UUID(int=1),
        event=TransferEvent.RECEIVED,
        logged_at=datetime(2026, 1, 1),
    )

    with pytest.raises(FrozenInstanceError):
        log.id = 2

    assert log.id == 1
