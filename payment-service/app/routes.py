import uuid, json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.db import get_pool
from app.models import CapturePaymentRequest, RefundRequest
from app.publisher import publish_event

router = APIRouter(prefix="/payments", tags=["payments"])

def _fmt(row) -> dict:
    return {
        "id": str(row["id"]),
        "transaction_ref": row["transaction_ref"],
        "amount_paise": row["amount_paise"],
        "amount_display": row["amount_paise"] / 100,
        "currency": row["currency"],
        "method": row["method"],
        "status": row["status"],
        "failure_reason": row.get("failure_reason"),
        "captured_at": row["captured_at"].isoformat() if row["captured_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }

@router.post("/capture", status_code=201)
async def capture_payment(req: CapturePaymentRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Idempotency check: if same key already exists, return existing record
        existing = await conn.fetchrow(
            "SELECT * FROM payments WHERE idempotency_key = $1", req.idempotency_key
        )
        if existing:
            return _fmt(existing)  # Return idempotent response, do NOT re-publish

        row = await conn.fetchrow("""
            INSERT INTO payments (transaction_ref, idempotency_key, amount_paise,
                                 currency, method, status, captured_at)
            VALUES ($1, $2, $3, $4, $5, 'CAPTURED', NOW())
            RETURNING *
        """, req.transaction_ref, req.idempotency_key, req.amount_paise,
            req.currency, req.method)

    await publish_event(
        event_type="payment.captured",
        transaction_ref=req.transaction_ref,
        entity_id=str(row["id"]),
        data={
            "payment_id": str(row["id"]),
            "amount_paise": req.amount_paise,
            "amount_display": req.amount_paise / 100,
            "currency": req.currency,
            "method": req.method,
            "status": "CAPTURED",
            "idempotency_key": req.idempotency_key,
        }
    )
    return _fmt(row)

@router.post("/{payment_id}/refund", status_code=201)
async def refund_payment(payment_id: str, req: RefundRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Idempotency check for refund
        existing_refund = await conn.fetchrow(
            "SELECT * FROM refunds WHERE idempotency_key = $1", req.idempotency_key
        )
        if existing_refund:
            return {"refund_id": str(existing_refund["id"]), "status": existing_refund["status"]}

        payment = await conn.fetchrow(
            "SELECT * FROM payments WHERE id = $1", uuid.UUID(payment_id)
        )
        if not payment:
            raise HTTPException(404, "Payment not found")
        if payment["status"] != "CAPTURED":
            raise HTTPException(400, f"Cannot refund payment in status: {payment['status']}")
        if req.amount_paise > payment["amount_paise"]:
            raise HTTPException(400, "Refund amount exceeds payment amount")

        refund = await conn.fetchrow("""
            INSERT INTO refunds (payment_id, amount_paise, reason, idempotency_key)
            VALUES ($1, $2, $3, $4) RETURNING *
        """, payment["id"], req.amount_paise, req.reason, req.idempotency_key)

        await conn.execute(
            "UPDATE payments SET status = 'REFUNDED', refund_id = $1, updated_at = NOW() WHERE id = $2",
            refund["id"], payment["id"]
        )

    await publish_event(
        event_type="payment.refunded",
        transaction_ref=payment["transaction_ref"],
        entity_id=str(refund["id"]),
        data={
            "refund_id": str(refund["id"]),
            "payment_id": payment_id,
            "amount_paise": req.amount_paise,
            "reason": req.reason,
        }
    )
    return {"refund_id": str(refund["id"]), "status": "INITIATED"}

@router.get("/{payment_id}")
async def get_payment(payment_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM payments WHERE id = $1", uuid.UUID(payment_id))
    if not row:
        raise HTTPException(404, "Payment not found")
    return _fmt(row)

@router.get("")
async def list_payments(transaction_ref: str | None = None, limit: int = 50):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if transaction_ref:
            rows = await conn.fetch(
                "SELECT * FROM payments WHERE transaction_ref = $1 ORDER BY created_at DESC",
                transaction_ref
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM payments ORDER BY created_at DESC LIMIT $1", limit
            )
    return [_fmt(r) for r in rows]
