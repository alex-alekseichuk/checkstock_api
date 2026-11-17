## Prerequisites

- **Docker** with the **Docker Compose** plugin — runs the whole stack: Postgres 18, one-shot dbmate migrations, and the API.
- **Python ≥ 3.12** — only if you develop / test the API locally instead of via Docker.
- **dbmate** — only if you want to apply the DB migrations outside the compose one-shot container.
- **`.env`** file at the project root with `DATABASE_URL` (already committed; used by the `api` and `db-migrate` compose services).

## Install

### Full stack with Docker Compose (recommended)

```bash
docker compose up --build
```

That starts:

- `db` — Postgres 18 (`checkstock` / `checkstock`), port `5432`;
- `db-migrate` — one-shot container that applies all dbmate migrations, then exits;
- `api` — the FastAPI service on port `8000`.

Check it is up: `curl http://localhost:8000/ping` → `{"status":"ok","message":"pong"}`.

Stop everything with:

```bash
docker compose down
```

### Local development (API and tests, no containerized app)

```bash
# 1. Start only the database
docker compose up db -d

# 2. Apply the migrations
cd checkstock_db
export DATABASE_URL="postgresql://checkstock:checkstock@localhost:5432/checkstock?sslmode=disable"
dbmate up
cd ..

# 3. Set up the API environment
cd checkstock_api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Run the service
PYTHONPATH=src uvicorn checkstock_api.main:app --host 0.0.0.0 --port 8000 --reload
```

The app reads the DSN from the `DATABASE_URL` environment variable; without it, it falls back to the compose credentials on `localhost:5432`.

## Tests

### Test business logic 

```bash
cd ./checkstock_api

# run only the models tests (this is what "by hand" means here)
.venv/bin/python -m pytest tests/checkstock_api/models -v

# one specific model
.venv/bin/python -m pytest tests/checkstock_api/models/test_transfer.py -v

# one specific test by name
.venv/bin/python -m pytest tests/checkstock_api/models/test_transfer.py -k receive -v

# run quietly, no per-test output
.venv/bin/python -m pytest tests/checkstock_api/models
```

### E2E tests

The E2E suite (`tests/e2e/`) exercises the full app — routes, services and repositories — against a real Postgres database. It creates a dedicated test database (`checkstock_e2e` by default), applies the dbmate migrations, truncates all tables before each test, and drops the database after the session ends. It needs the `db` compose service:

```bash
# 1. Start the database only (from the repo root)
docker compose up db -d

# 2. Run the E2E suite
cd ./checkstock_api
.venv/bin/python -m pytest tests/e2e
```

If the database is not reachable, the whole suite is skipped with an explanatory message instead of failing. Point the suite at a different database with `CHECKSTOCK_E2E_DATABASE_URL`:

```bash
CHECKSTOCK_E2E_DATABASE_URL="postgresql://checkstock:checkstock@localhost:5432/checkstock_e2e" .venv/bin/python -m pytest tests/e2e
```

## TODO:
- on store close, transfer its stocks to another store
- config
- logger
- auth.
- swagger
- separate repositories at line of CQRS
- move asyncpg to db module only, by clean arch.

## Glossary

| Term | Meaning |
| --- | --- |
| Item (артикул) | A product, uniquely identified by its SKU. Can be stocked at one or more FF stores. |
| SKU | The item's article number; unique per item. |
| FF (fulfillment store) | A fulfillment center (склад фулфилмента) that physically holds item stock. In the schema, rows of `stock.stores`. |
| Stock (остатки) | The on-hand quantity of one item at one FF store (row of `stock.stock`). |
| Reserved (резерв) | The part of the stock blocked for FBS orders; always `reserved <= quantity`. |
| Available | `quantity - reserved` — what can be ordered or moved from a store. |
| FBO | Fulfillment via the marketplace: stock leaves the FF and is counted "in transit" to the marketplace warehouse until receipt. |
| FBS | Fulfillment by the seller: the order is shipped directly to the customer; until shipment the stock is reserved at the FF. |
| Inbound (приход) | Stock receipt at an FF — the initial stocking event. |
| Transfer (перемещение) | A stock movement: an FF→FF transfer or a shipment toward an FBO / FBS destination (row of `stock.transfers`). |
| In transit (в пути) | Stock that left its source FF but has not yet been received at the destination. |
| Receipt (приёмка) | Arrival of stock at the destination; marks the transfer as `received`. |
| Transfer log | One row of `stock.transfer_logs` — a single state-change event of a transfer (operation history). |
| Shortage (нехватка) | The chosen FF does not have enough stock, although the total across all FFs is sufficient. |
