from fastapi import APIRouter, Request, Header, HTTPException
from typing import Optional
from app.services.ingestion_service import IngestionService

router = APIRouter(tags=["ingest"])
_service = IngestionService()


def get_ingestion_service() -> IngestionService:
    return _service


@router.post("/webhooks/{source}")
async def receive_webhook(
    source: str,
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_transaction_ref: Optional[str] = Header(None, alias="X-Transaction-Ref"),
):
    body_bytes = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    headers = dict(request.headers)
    if x_signature:
        headers["x-signature"] = x_signature
    if x_transaction_ref:
        headers["x-transaction-ref"] = x_transaction_ref

    result = await _service.ingest(
        source=source,
        raw_payload=payload,
        raw_bytes=body_bytes,
        headers=headers,
    )
    return result


@router.post("/ingest")
async def ingest_direct(request: Request):
    payload = await request.json()
    source = payload.get("source_system") or payload.get("source", "generic")
    return await _service.ingest(source=source, raw_payload=payload)

