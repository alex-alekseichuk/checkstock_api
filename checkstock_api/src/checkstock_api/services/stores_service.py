"""Service layer for stores, on top of ``StoresRepo``."""

from __future__ import annotations

from uuid import UUID

from checkstock_api.models.store import Store, StoreStatus
from checkstock_api.repositories.stores_repo import StoreRepo


class StoresService:
    """Business operations for stores."""

    def __init__(self, stores_repo: StoreRepo) -> None:
        self.stores_repo = stores_repo

    async def add_store(
        self,
        title: str,
        status: StoreStatus = StoreStatus.ACTIVE,
        id: UUID | None = None,
    ) -> Store:
        """Add a new store and return it.

        If ``id`` is given it becomes the primary key; otherwise the
        database default (``uuidv7``) generates it.
        """
        return await self.stores_repo.insert(title, status, id)

    async def close_store(self, id: UUID) -> Store | None:
        """Close a store (status -> ``closed``).

        Returns the updated store, or ``None`` if no store with ``id``
        exists.
        """
        return await self.stores_repo.update(id, status=StoreStatus.CLOSED)

    async def activate_store(self, id: UUID) -> Store | None:
        """Re-activate a store (status -> ``active``).

        Returns the updated store, or ``None`` if no store with ``id``
        exists.
        """
        return await self.stores_repo.update(id, status=StoreStatus.ACTIVE)
