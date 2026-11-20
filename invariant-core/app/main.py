import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.base import init_pool, close_pool
from app.routes.ingest import router as ingest_router
from app.routes.transactions import router as transactions_router
from app.routes.incidents import router as incidents_router
from app.routes.reconciliation import router as reconciliation_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("invariant_core_starting")
    await init_pool()
    yield
    await close_pool()
    logger.info("invariant_core_stopped")


app = FastAPI(
    title="Invariant Core Integrity Engine",
    description="Cross-system business transaction integrity, correlation, invariant checks, and reconciliation platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ingest_router)
app.include_router(transactions_router)
app.include_router(incidents_router)
app.include_router(reconciliation_router)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    return {"status": "ok"}

