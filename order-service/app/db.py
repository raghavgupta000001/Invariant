import os, asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_ref TEXT NOT NULL UNIQUE,  -- e.g. "TXN-1042"
    customer_email  TEXT NOT NULL,
    customer_name   TEXT NOT NULL,
    items           JSONB NOT NULL,  -- [{sku, name, qty, unit_price_paise}]
    total_amount_paise BIGINT NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'INR',
    status          TEXT NOT NULL DEFAULT 'CREATED'
                    CHECK (status IN ('CREATED', 'PAID', 'FULFILLED', 'CANCELLED')),
    notes           JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID NOT NULL REFERENCES orders(id),
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL,
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
