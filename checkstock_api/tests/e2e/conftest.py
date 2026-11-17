"""Session setup for the e2e suite: a disposable test database.

Lifecycle per pytest session:

1. connect to the Postgres server (``checkstock`` maintenance database);
2. drop and recreate the test database (``checkstock_e2e`` by default);
3. apply the dbmate migrations from ``checkstock_db/db/migrations``;
4. open the app with ``TestClient`` (its lifespan opens the asyncpg pool);
5. truncate all tables before every test so each test sees a clean slate;
6. drop the test database after the session.

If the server is not reachable, the whole suite is skipped.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import asyncpg
import pytest
from fastapi.testclient import TestClient

# Repo root: checkstock_api/tests/e2e/conftest.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "checkstock_db" / "db" / "migrations"

# A dedicated database, so the suite never touches the dev database.
E2E_DSN = os.environ.get(
    "CHECKSTOCK_E2E_DATABASE_URL",
    "postgresql://checkstock:checkstock@localhost:5432/checkstock_e2e",
)
_MAINTENANCE_DB = "checkstock"

# The app reads DATABASE_URL at import time; point it at the test database
# *before* importing the app module.
os.environ["DATABASE_URL"] = E2E_DSN

from checkstock_api.main import app  # noqa: E402


def _admin_dsn() -> str:
    """DSN of the maintenance database on the same server."""
    parts = urlsplit(E2E_DSN)
    return (
        f"postgresql://{parts.username}:{parts.password}"
        f"@{parts.hostname}:{parts.port}/{_MAINTENANCE_DB}"
    )


def _db_name() -> str:
    return urlsplit(E2E_DSN).path.lstrip("/") or "checkstock_e2e"


def _up_part(sql: str) -> str:
    """The ``-- migrate:up`` section of a dbmate migration file."""
    up, _, _down = sql.partition("-- migrate:down")
    return up.replace("-- migrate:up", "").strip()


async def _ensure_fresh_database() -> None:
    db_name = _db_name()
    # asyncpg auto-commits each statement outside an explicit transaction,
    # which is what CREATE/DROP DATABASE require.
    admin = await asyncpg.connect(_admin_dsn())
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await admin.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin.close()


async def _apply_migrations() -> None:
    conn = await asyncpg.connect(E2E_DSN)
    try:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            sql = _up_part(path.read_text(encoding="utf-8"))
            if sql:
                await conn.execute(sql)
    finally:
        await conn.close()


async def _truncate_tables() -> None:
    conn = await asyncpg.connect(E2E_DSN)
    try:
        await conn.execute(
            "TRUNCATE stock.transfer_logs, stock.transfers, stock.stock, "
            "stock.items, stock.stores"
        )
    finally:
        await conn.close()


async def _drop_database() -> None:
    db_name = _db_name()
    admin = await asyncpg.connect(_admin_dsn())
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    finally:
        await admin.close()


def _run(coro) -> Any:
    return asyncio.run(coro)


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Test client bound to the app, running against a fresh test database."""
    try:
        _run(_ensure_fresh_database())
        _run(_apply_migrations())
    except Exception as exc:
        pytest.skip(
            f"e2e suite skipped: database not reachable at {E2E_DSN} ({exc}). "
            "Start it with: docker compose up db -d"
        )

    with TestClient(app) as test_client:
        yield test_client

    # After the TestClient exits, the app's pool is closed, so the database
    # can be dropped.
    _run(_drop_database())


@pytest.fixture(autouse=True)
def clean_tables(client: TestClient) -> Iterator[None]:
    """Truncate all tables before each test: every test starts clean."""
    _run(_truncate_tables())
    yield


@pytest.fixture
def db_query():
    """Synchronous SQL access for white-box assertions on tables with no
    HTTP route (e.g. ``stock.transfer_logs``). Usage in a test::

        rows = db_query("SELECT event FROM stock.transfer_logs ...", transfer_id)
    """

    async def _fetch(sql: str, *args: Any) -> list:
        conn = await asyncpg.connect(E2E_DSN)
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    def run(sql: str, *args: Any) -> list:
        return asyncio.run(_fetch(sql, *args))

    return run
