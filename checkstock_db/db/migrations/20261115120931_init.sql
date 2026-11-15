-- migrate:up

-- CheckStock initial schema, per the ER diagram in db/er.md.
--
-- All tables live in the `stock` schema. A single product (SKU) is stocked
-- at one or more fulfillment centers (FF stores); part of the on-hand
-- stock can be reserved. Stock moves between FFs (and toward FBO / FBS
-- destinations) via transfers; every state change of a transfer is
-- recorded in transfer_logs.
--
-- PostgreSQL has no unsigned type: the "unsigned int" columns from the
-- ER diagram are `integer` guarded by CHECK (>= 0); the transfer_logs
-- identity PK is positive by construction.

CREATE SCHEMA stock;

-- Store status: 'active' (receiving stock and selling) or 'closed'.
CREATE TYPE stock.store_status AS ENUM ('active', 'closed');

-- Transfer type: 'inbound', inter-FF 'transfer', FBO ('ship_fbo') or
-- FBS ('ship_fbs') shipment.
CREATE TYPE stock.transfer_type AS ENUM ('inbound', 'transfer', 'ship_fbo', 'ship_fbs');

-- Transfer state: 'reserved' (blocked for an FBS order), 'canceled'
-- (reservation canceled), 'in_transit' (being moved) or 'received'
-- (arrived).
CREATE TYPE stock.transfer_status AS ENUM ('reserved', 'canceled', 'in_transit', 'received');

-- Transfer lifecycle event recorded in transfer_logs.
CREATE TYPE stock.transfer_event AS ENUM ('inbound', 'sent', 'received', 'reserved', 'canceled');

-- Products (артикулы).
CREATE TABLE stock.items (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    sku text NOT NULL UNIQUE,
    title text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Fulfillment centers / FF stores.
CREATE TABLE stock.stores (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    title text NOT NULL,
    status stock.store_status NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now()
);

-- On-hand stock per item per FF store.
-- `stock_id` is the FF store (склад) holding this stock;
-- `reserved` is stock blocked for orders.
CREATE TABLE stock.stock (
    item_id uuid NOT NULL REFERENCES stock.items (id),
    stock_id uuid NOT NULL REFERENCES stock.stores (id),
    quantity integer NOT NULL DEFAULT 0,
    reserved integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (item_id, stock_id),
    CHECK (quantity >= 0),
    CHECK (reserved >= 0),
    CHECK (quantity >= reserved)
);

-- Movements: inbound receipt, inter-FF transfer, or FBO / FBS shipment.
-- `src_stock_id` / `dest_stock_id` are the source and destination FF
-- stores (NULL when the movement has no FF store on that side).
CREATE TABLE stock.transfers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id uuid NOT NULL REFERENCES stock.items (id),
    quantity integer NOT NULL,
    type stock.transfer_type NOT NULL DEFAULT 'inbound',
    src_stock_id uuid REFERENCES stock.stores (id),
    dest_stock_id uuid REFERENCES stock.stores (id),
    status stock.transfer_status NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (quantity > 0),
    CHECK (src_stock_id <> dest_stock_id)
);

-- State-change history of a transfer: one row per event.
CREATE TABLE stock.transfer_logs (
    id integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    transfer_id uuid NOT NULL REFERENCES stock.transfers (id),
    event stock.transfer_event NOT NULL,
    logged_at timestamptz NOT NULL DEFAULT now()
);

-- migrate:down

DROP SCHEMA stock CASCADE;
