from fastapi import APIRouter
import asyncpg

router = APIRouter(tags=["health"])

@router.get("/health/live")
async def liveness():
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness():
    # Could add DB ping here if needed
    return {"status": "ok"}
