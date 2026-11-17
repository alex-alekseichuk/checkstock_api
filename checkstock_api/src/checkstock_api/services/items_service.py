"""Service layer for items, on top of ``ItemsRepo``."""

from __future__ import annotations

from uuid import UUID

from checkstock_api.models.item import Item
from checkstock_api.repositories.items_repo import ItemRepo


class ItemsService:
    """Business operations for items."""

    def __init__(self, items_repo: ItemRepo) -> None:
        self.items_repo = items_repo

    async def add_item(
        self,
        sku: str,
        title: str,
        id: UUID | None = None,
    ) -> Item:
        """Add a new item and return it.

        If ``id`` is given it becomes the primary key; otherwise the
        database default (``uuidv7``) generates it.
        """
        return await self.items_repo.insert_item(sku, title, id)
