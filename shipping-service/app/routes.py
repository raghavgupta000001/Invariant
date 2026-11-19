import uuid, json, random, string
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from app.db import get_pool
from app.models import CreateShipmentRequest
from app.publisher import publish_event
from app import failure_state

router = APIRouter(prefix="/shipments", tags=["shipments"])


def _generate_tracking_number(carrier: str) -> str:
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    prefixes = {"BLUEDART": "BD", "DTDC": "DT", "DELHIVERY": "DL", "EKART": "EK"}
    return f"{prefixes.get(carrier, 'SH')}{suffix}"


def _fmt(row) -> dict:
    return {
        "id": str(row["id"]),
        "transaction_ref": row["transaction_ref"],
        "tracking_number": row["tracking_number"],
        "carrier": row["carrier"],
        "status": row["status"],
        "recipient_name": row["recipient_name"],
        "recipient_email": row["recipient_email"],
        "estimated_delivery": row["estimated_delivery"].isoformat() if row["estimated_delivery"] else None,
        "failure_reason": row.get("failure_reason"),
        "created_at": row["created_at"].isoformat(),
    }


@router.post("", status_code=201)
async def create_shipment(req: CreateShipmentRequest):
    # Failure mode: shipment creation fails
    if failure_state.is_active("shipment_creation_fails"):
        await publish_event(
            event_type="shipment.failed",
            transaction_ref=req.transaction_ref,
            entity_id="N/A",
            data={"reason": "SIMULATED_SHIPMENT_FAILURE", "transaction_ref": req.transaction_ref}
        )
        raise HTTPException(503, "Shipping provider temporarily unavailable [SIMULATED]")

    pool = await get_pool()
    tracking_number = _generate_tracking_number(req.carrier)
    estimated = (datetime.now(timezone.utc) + timedelta(days=3)).date()

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM shipments WHERE transaction_ref = $1", req.transaction_ref
        )
        if existing:
            raise HTTPException(409, "Shipment already created for this transaction")

        row = await conn.fetchrow("""
            INSERT INTO shipments (transaction_ref, sales_order_id, carrier, tracking_number,
                                  recipient_name, recipient_email, delivery_address, estimated_delivery)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8) RETURNING *
        """, req.transaction_ref, req.sales_order_id, req.carrier, tracking_number,
            req.recipient_name, req.recipient_email,
            json.dumps(req.delivery_address.model_dump()), estimated)

        await conn.execute("""
            INSERT INTO tracking_events (shipment_id, status, notes)
            VALUES ($1, 'CREATED', 'Shipment created and awaiting pickup')
        """, row["id"])

    await publish_event(
        event_type="shipment.created",
        transaction_ref=req.transaction_ref,
        entity_id=str(row["id"]),
        data={
            "shipment_id": str(row["id"]),
            "tracking_number": tracking_number,
            "carrier": req.carrier,
            "recipient_email": req.recipient_email,
            "estimated_delivery": estimated.isoformat(),
        }
    )
    return _fmt(row)


@router.get("/{shipment_id}")
async def get_shipment(shipment_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM shipments WHERE id::text = $1 OR transaction_ref = $1", shipment_id
        )
    if not row:
        raise HTTPException(404, "Shipment not found")
    return _fmt(row)


@router.get("")
async def list_shipments(limit: int = 50):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM shipments ORDER BY created_at DESC LIMIT $1", limit)
    return [_fmt(r) for r in rows]


@router.post("/failure")
async def set_failure(mode: str, active: bool = True):
    if active:
        failure_state.set_failure(mode)
    else:
        failure_state.clear_failure(mode)
    return {"mode": mode, "active": active}
