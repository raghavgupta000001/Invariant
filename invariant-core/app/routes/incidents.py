from fastapi import APIRouter, HTTPException
from typing import Optional
from app.routes.ingest import get_ingestion_service

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
async def list_incidents(
    transaction_ref: Optional[str] = None,
    state: Optional[str] = None,
    severity: Optional[str] = None,
):
    service = get_ingestion_service()
    incidents = service.incident_service.list_incidents(
        transaction_ref=transaction_ref, state=state, severity=severity
    )
    return {"count": len(incidents), "incidents": incidents}


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    service = get_ingestion_service()
    inc = service.incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return inc


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str):
    service = get_ingestion_service()
    inc = service.incident_service.update_incident_state(incident_id, "RESOLVED")
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return inc

