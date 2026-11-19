import os, asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_ref TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    amount_paise    BIGINT NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'INR',
    method          TEXT NOT NULL DEFAULT 'upi'
                    CHECK (method IN ('upi', 'card', 'netbanking', 'wallet')),
    status          TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING', 'CAPTURED', 'FAILED', 'REFUNDED')),
    failure_reason  TEXT,
    refund_id       UUID,
    captured_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refunds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id      UUID NOT NULL REFERENCES payments(id),
    amount_paise    BIGINT NOT NULL,
    reason          TEXT,
    status          TEXT NOT NULL DEFAULT 'INITIATED'
                    CHECK (status IN ('INITIATED', 'PROCESSED', 'FAILED')),
    idempotency_key TEXT NOT NULL UNIQUE,
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
