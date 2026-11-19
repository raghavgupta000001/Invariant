import os, asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS sales_orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_ref TEXT NOT NULL UNIQUE,
    customer_id     TEXT NOT NULL,
    customer_email  TEXT NOT NULL,
    line_items      JSONB NOT NULL,
    total_amount_paise BIGINT NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'INR',
    status          TEXT NOT NULL DEFAULT 'OPEN'
                    CHECK (status IN ('OPEN', 'CONFIRMED', 'INVOICED', 'CANCELLED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory_holds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sales_order_id  UUID REFERENCES sales_orders(id),
    transaction_ref TEXT NOT NULL,
    sku             TEXT NOT NULL,
    qty_reserved    INT NOT NULL CHECK (qty_reserved > 0),
    status          TEXT NOT NULL DEFAULT 'RESERVED'
                    CHECK (status IN ('RESERVED', 'RELEASED', 'FULFILLED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sales_order_id  UUID NOT NULL REFERENCES sales_orders(id),
    transaction_ref TEXT NOT NULL,
    invoice_number  TEXT NOT NULL UNIQUE,
    amount_paise    BIGINT NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'INR',
    status          TEXT NOT NULL DEFAULT 'ISSUED'
                    CHECK (status IN ('ISSUED', 'PAID', 'VOIDED')),
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_URL"], min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await conn.execute(CREATE_SCHEMA)

async def get_pool() -> asyncpg.Pool:
    return _pool
