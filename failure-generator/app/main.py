import structlog
from fastapi import FastAPI
from app.routes import router

logger = structlog.get_logger()

app = FastAPI(
    title="Invariant Failure Generator",
    description="50-scenario reproducible failure injection and benchmark runner for Invariant",
    version="0.1.0",
)

app.include_router(router)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    return {"status": "ok"}

