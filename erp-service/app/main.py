import os, structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from app.db import init_db
from app.publisher import init_publisher
from app.routes import router

load_dotenv()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("erp-service starting")
    await init_db()
    await init_publisher()
    yield
    logger.info("erp-service stopping")

app = FastAPI(title="ERP Service", version="0.1.0", lifespan=lifespan)
app.include_router(router)

@app.get("/health/live")
async def live(): return {"status": "ok"}

@app.get("/health/ready")
async def ready(): return {"status": "ok"}
