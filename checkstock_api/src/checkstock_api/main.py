"""checkstock API service.

Run locally (from the project root):
    PYTHONPATH=src uvicorn checkstock_api.main:app --host 0.0.0.0 --port 8000 --reload

The database is read from the ``DATABASE_URL`` environment variable
(``postgresql+asyncpg://`` is accepted too); locally it defaults to the
``docker-compose.yml`` credentials on ``localhost:5432``.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from checkstock_api.common.db import Database
from checkstock_api.repositories.items_repo import ItemRepo
from checkstock_api.repositories.stores_repo import StoreRepo
from checkstock_api.repositories.stock_repo import StockRepo
from checkstock_api.repositories.transfer_repo import TransferRepo
from checkstock_api.routes.items_routes import create_items_router
from checkstock_api.routes.stock_routes import create_stock_router
from checkstock_api.routes.stores_routes import create_stores_router
from checkstock_api.routes.transfer_routes import create_transfers_router
from checkstock_api.services.items_service import ItemsService
from checkstock_api.services.stock_service import StockService
from checkstock_api.services.stores_service import StoresService
from checkstock_api.services.transfer_service import TransferService

DEFAULT_DATABASE_URL = "postgresql://checkstock:checkstock@localhost:5432/checkstock"


def database_url() -> str:
    """``DATABASE_URL`` as an asyncpg DSN.

    Accepts both the plain ``postgresql://`` form and the
    ``postgresql+asyncpg://`` form used in ``docker-compose.yml``.
    """
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the asyncpg pool on startup, close it on shutdown."""
    await app.state.db.connect()
    try:
        yield
    finally:
        await app.state.db.close()


app = FastAPI(title="checkstock API", lifespan=lifespan)
app.state.db = Database(database_url())
app.include_router(create_items_router(ItemsService(ItemRepo(app.state.db))))
app.include_router(
    create_stores_router(StoresService(StoreRepo(app.state.db), StockRepo(app.state.db)))
)
app.include_router(create_stock_router(StockService(StockRepo(app.state.db))))
app.include_router(
    create_transfers_router(
        TransferService(
            app.state.db,
            ItemRepo(app.state.db),
            StoreRepo(app.state.db),
            StockRepo(app.state.db),
            TransferRepo(app.state.db),
        )
    )
)


@app.get("/ping")
async def ping() -> dict[str, str]:
    """Health-check / liveness endpoint (async, no thread pool)."""
    return {"status": "ok", "message": "pong"}
