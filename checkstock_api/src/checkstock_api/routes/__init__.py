"""FastAPI routers, composed of services."""

from checkstock_api.routes.items_routes import create_items_router
from checkstock_api.routes.stores_routes import create_stores_router

__all__ = [
    "create_items_router",
    "create_stores_router",
]
