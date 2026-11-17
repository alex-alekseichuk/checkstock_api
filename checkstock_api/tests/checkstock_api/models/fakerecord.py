"""A minimal stand-in for ``asyncpg.Record``.

``asyncpg.Record`` is accessed by column name (``row["col"]``), and the
model ``from_row`` classmethods only use that interface, so a dict-backed
class is enough for unit tests without a database.
"""

from typing import Any


class FakeRow:
    """Dictionary-backed fake of ``asyncpg.Record`` with key-based access."""

    def __init__(self, **fields: Any) -> None:
        self._fields = fields

    def __getitem__(self, key: str) -> Any:
        return self._fields[key]

    def __contains__(self, key: str) -> bool:
        return key in self._fields

    def __repr__(self) -> str:
        return f"FakeRow({self._fields!r})"
