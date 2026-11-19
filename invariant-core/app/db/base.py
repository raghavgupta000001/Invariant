import os
import asyncpg
import structlog
from typing import Optional

logger = structlog.get_logger()

_pool: Optional[asyncpg.Pool] = None


async def init_pool(dsn: Optional[str] = None, min_size: int = 2, max_size: int = 10) -> Optional[asyncpg.Pool]:
    global _pool
    db_url = dsn or os.environ.get("DATABASE_URL", "postgresql://invariant:invariant@localhost:5432/invariant_core_db")
    try:
        _pool = await asyncpg.create_pool(dsn=db_url, min_size=min_size, max_size=max_size)
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            async with _pool.acquire() as conn:
                await conn.execute(schema_sql)
        logger.info("database_pool_initialized", dsn=db_url)
        return _pool
    except Exception as e:
        logger.warning("database_pool_init_failed", error=str(e))
        _pool = None
        return None


async def get_pool() -> Optional[asyncpg.Pool]:
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

