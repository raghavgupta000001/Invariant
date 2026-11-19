import uuid, json
from fastapi import APIRouter, HTTPException
from app.db import get_pool
from app.models import CreateSalesOrderRequest, ReserveInventoryRequest, GenerateInvoiceRequest
from app.publisher import publish_event
from app import failure_state

router = APIRouter(tags=["erp"])

@router.post("/erp/orders", status_code=201)
async def create_sales_order(req: CreateSalesOrderRequest):
    # SILENT FAILURE: return 200 but skip DB write
    if failure_state.is_active("erp_silent_failure"):
        return {
            "id": str(uuid.uuid4()),  # Fake ID
            "transaction_ref": req.transaction_ref,
            "status": "OPEN",
            "note": "__SIMULATED_SILENT_FAILURE__",
        }

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Validate no duplicate
        existing = await conn.fetchrow(
            "SELECT id FROM sales_orders WHERE transaction_ref = $1", req.transaction_ref
        )
        if existing:
            raise HTTPException(409, f"Sales order already exists for {req.transaction_ref}")

        row = await conn.fetchrow("""
            INSERT INTO sales_orders (transaction_ref, customer_id, customer_email,
                                     line_items, total_amount_paise)
            VALUES ($1, $2, $3, $4::jsonb, $5) RETURNING *
        """, req.transaction_ref, req.customer_id, req.customer_email,
            json.dumps([i.model_dump() for i in req.line_items]), req.total_amount_paise)

    await publish_event(
        event_type="erp.order_created",
        transaction_ref=req.transaction_ref,
        entity_id=str(row["id"]),
        data={
            "sales_order_id": str(row["id"]),
            "customer_id": req.customer_id,
            "total_amount_paise": req.total_amount_paise,
            "status": "OPEN",
        }
    )
    return {
        "id": str(row["id"]),
        "transaction_ref": row["transaction_ref"],
        "customer_id": row["customer_id"],
        "status": row["status"],
        "total_amount_paise": row["total_amount_paise"],
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/erp/orders/{transaction_ref}")
async def get_sales_order(transaction_ref: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sales_orders WHERE transaction_ref = $1", transaction_ref
        )
    if not row:
        raise HTTPException(404, "Sales order not found")
    return {
        "id": str(row["id"]),
        "transaction_ref": row["transaction_ref"],
        "customer_id": row["customer_id"],
        "status": row["status"],
        "total_amount_paise": row["total_amount_paise"],
        "created_at": row["created_at"].isoformat(),
    }


@router.post("/erp/inventory/reserve", status_code=201)
async def reserve_inventory(req: ReserveInventoryRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        sales_order = await conn.fetchrow(
            "SELECT id FROM sales_orders WHERE id = $1",
            uuid.UUID(req.sales_order_id)
        )
        if not sales_order:
            raise HTTPException(404, "Sales order not found")

        hold_ids = []
        for item in req.items:
            hold = await conn.fetchrow("""
                INSERT INTO inventory_holds (sales_order_id, transaction_ref, sku, qty_reserved)
                VALUES ($1, $2, $3, $4) RETURNING id
            """, sales_order["id"], req.transaction_ref, item.sku, item.qty)
            hold_ids.append(str(hold["id"]))

    await publish_event(
        event_type="erp.inventory_reserved",
        transaction_ref=req.transaction_ref,
        entity_id=req.sales_order_id,
        data={"hold_ids": hold_ids, "items": [i.model_dump() for i in req.items]}
    )
    return {"hold_ids": hold_ids, "status": "RESERVED"}


@router.post("/erp/invoices", status_code=201)
async def generate_invoice(req: GenerateInvoiceRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
        inv = await conn.fetchrow("""
            INSERT INTO invoices (sales_order_id, transaction_ref, invoice_number, amount_paise)
            VALUES ($1, $2, $3, $4) RETURNING *
        """, uuid.UUID(req.sales_order_id), req.transaction_ref, invoice_number, req.amount_paise)

    await publish_event(
        event_type="erp.invoice_generated",
        transaction_ref=req.transaction_ref,
        entity_id=str(inv["id"]),
        data={"invoice_id": str(inv["id"]), "invoice_number": invoice_number, "amount_paise": req.amount_paise}
    )
    return {
        "id": str(inv["id"]),
        "invoice_number": invoice_number,
        "amount_paise": req.amount_paise,
        "status": "ISSUED",
        "issued_at": inv["issued_at"].isoformat(),
    }


@router.post("/erp/failure")
async def set_failure(mode: str, active: bool = True):
    """Control endpoint for failure injection — called by simulator orchestrator."""
    if active:
        failure_state.set_failure(mode)
    else:
        failure_state.clear_failure(mode)
    return {"mode": mode, "active": active}
