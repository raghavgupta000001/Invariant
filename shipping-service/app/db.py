import os, asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS shipments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_ref TEXT NOT NULL UNIQUE,
    sales_order_id  TEXT NOT NULL,
    carrier         TEXT NOT NULL DEFAULT 'BLUEDART'
                    CHECK (carrier IN ('BLUEDART', 'DTDC', 'DELHIVERY', 'EKART')),
    tracking_number TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'CREATED'
                    CHECK (status IN ('CREATED', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'FAILED')),
    recipient_name  TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    delivery_address JSONB NOT NULL,
    estimated_delivery DATE,
    failure_reason  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tracking_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id     UUID NOT NULL REFERENCES shipments(id),
    status          TEXT NOT NULL,
    location        TEXT,
    notes           TEXT,
    event_time      TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
