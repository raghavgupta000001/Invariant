import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from app.client import close_all
from app.routes import router

load_dotenv()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("simulator_starting")
    yield
    await close_all()
    logger.info("simulator_stopped")


app = FastAPI(
    title="Invariant Simulator",
    description=(
        "Orchestrates the four business microservices to run end-to-end transaction "
        "scenarios — both happy paths and injected failures — giving Invariant's "
        "integrity engine real anomalies to detect."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    return {"status": "ok"}

