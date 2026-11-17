"""Service layer for stores, on top of ``StoresRepo``."""

from __future__ import annotations

from uuid import UUID

from checkstock_api.models.store import Store, StoreStatus, StoreError
from checkstock_api.repositories.stock_repo import StockRepo
from checkstock_api.repositories.stores_repo import StoreRepo


class StoresService:
    """Business operations for stores."""

    def __init__(self, stores_repo: StoreRepo, stock_repo: StockRepo) -> None:
        self.stock_repo = stock_repo
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
        return await self.stores_repo.insert_store(title, status, id)

    async def close_store(self, id: UUID) -> Store:
        """Close a store (status -> ``closed``).

        The store must hold no on-hand stock: closing a store that still
        has stock raises ``StoreError`` 409. Raises ``StoreError`` 404
        when no store with ``id`` exists.
        """
        async with self.stores_repo.db.transaction() as connection:
            store = await self.stores_repo.lock_store(connection, id)
            if store is None:
                raise StoreError(404, f"store with id {id!r} not found")
            if not await self.stock_repo.is_store_empty(id, connection=connection):
                raise StoreError(409, f"store with id {id!r} is not empty")
            return await self.stores_repo.update_store(
                id, title=None, status=StoreStatus.CLOSED, connection=connection
            )

    async def activate_store(self, id: UUID) -> Store | None:
        """Re-activate a store (status -> ``active``).

        Returns the updated store, or ``None`` if no store with ``id``
        exists.
        """
        return await self.stores_repo.update_store(id, status=StoreStatus.ACTIVE)
