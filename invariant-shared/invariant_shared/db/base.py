import asyncpg, os
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

async def init_pool(dsn: str | None = None, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=dsn or os.environ["DATABASE_URL"],
            min_size=min_size,
            max_size=max_size
        )
    return _pool

async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool not initialized. Call init_pool() first.")
    return _pool

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
