import structlog
from fastapi import FastAPI
from app.routes import router

logger = structlog.get_logger()

app = FastAPI(
    title="Invariant Saga Recovery & Compensation Engine",
    description="Saga compensation plans, dry-run simulations, human approval gating, and idempotent recovery.",
    version="0.1.0",
)

app.include_router(router)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    return {"status": "ok"}

