from fastapi import APIRouter, HTTPException
from typing import Optional
from app.routes.ingest import get_ingestion_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
async def list_transactions(state: Optional[str] = None):
    service = get_ingestion_service()
    txns = service.state_machine.list_transactions()
    if state:
        txns = [t for t in txns if t["state"] == state]
    return {"count": len(txns), "transactions": txns}


@router.get("/{txn_ref}")
async def get_transaction(txn_ref: str):
    service = get_ingestion_service()
    txn = service.state_machine.get_transaction(txn_ref)
    if not txn:
        raise HTTPException(status_code=404, detail=f"Transaction {txn_ref} not found")

    refs = service.correlator.get_references(txn_ref)
    return {
        **txn,
        "entity_references": refs,
    }


@router.get("/{txn_ref}/timeline")
async def get_transaction_timeline(txn_ref: str):
    service = get_ingestion_service()
    txn = service.state_machine.get_transaction(txn_ref)
    if not txn:
        raise HTTPException(status_code=404, detail=f"Transaction {txn_ref} not found")

    return {
        "transaction_ref": txn_ref,
        "state": txn["state"],
        "events": txn["events"],
        "steps": txn["steps"],
    }

