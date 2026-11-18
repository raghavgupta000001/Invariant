import uuid
import json
from fastapi import APIRouter, HTTPException
from app.db import get_pool
from app.models import CreateOrderRequest, OrderResponse, CancelOrderRequest
from app.publisher import publish_event

router = APIRouter(prefix="/orders", tags=["orders"])

def _fmt_order(row) -> dict:
    return {
        "id": str(row["id"]),
        "transaction_ref": row["transaction_ref"],
        "customer_email": row["customer_email"],
        "customer_name": row["customer_name"],
        "items": row["items"],
        "total_amount_paise": row["total_amount_paise"],
        "total_amount_display": row["total_amount_paise"] / 100,
        "currency": row["currency"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
    }

@router.post("", status_code=201)
async def create_order(req: CreateOrderRequest):
    pool = await get_pool()
    transaction_ref = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    total = req.total_amount_paise
    items_json = [item.model_dump() for item in req.items]
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO orders (transaction_ref, customer_email, customer_name, 
                               items, total_amount_paise, notes)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6::jsonb)
            RETURNING *
        """, transaction_ref, req.customer_email, req.customer_name,
            json.dumps(items_json), total,
            json.dumps(req.notes))
        
        await conn.execute("""
            INSERT INTO order_events (order_id, event_type, payload)
            VALUES ($1, 'order.created', $2::jsonb)
        """, row["id"], json.dumps({"status": "CREATED"}))
    
    # Publish event to Pub/Sub
    await publish_event(
        event_type="order.created",
        transaction_ref=transaction_ref,
        entity_id=str(row["id"]),
        data={
            "order_id": str(row["id"]),
            "customer_email": req.customer_email,
            "customer_name": req.customer_name,
            "items": items_json,
            "total_amount_paise": total,
            "currency": "INR",
            "status": "CREATED",
        }
    )
    
    return _fmt_order(row)

@router.get("/{order_id}")
async def get_order(order_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM orders WHERE id::text = $1 OR transaction_ref = $1", order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return _fmt_order(row)

@router.get("")
async def list_orders(limit: int = 50):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM orders ORDER BY created_at DESC LIMIT $1", limit)
    return [_fmt_order(r) for r in rows]

@router.post("/{order_id}/cancel")
async def cancel_order(order_id: str, req: CancelOrderRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE orders SET status = 'CANCELLED', updated_at = NOW()
            WHERE (id::text = $1 OR transaction_ref = $1) AND status != 'CANCELLED'
            RETURNING *
        """, order_id)
        if not row:
            raise HTTPException(status_code=404, detail="Order not found or already cancelled")
        
        await conn.execute("""
            INSERT INTO order_events (order_id, event_type, payload)
            VALUES ($1, 'order.cancelled', $2::jsonb)
        """, row["id"], json.dumps({"reason": req.reason}))
    
    await publish_event(
        event_type="order.cancelled",
        transaction_ref=row["transaction_ref"],
        entity_id=str(row["id"]),
        data={"order_id": str(row["id"]), "reason": req.reason, "status": "CANCELLED"}
    )
    return _fmt_order(row)
