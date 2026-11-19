import uuid
import structlog
from fastapi import APIRouter
from app.client import get_client
from app.models import SimulateRequest, SimulationResult, StepResult, FailureMode

logger = structlog.get_logger()
router = APIRouter()


async def _post(service: str, path: str, json: dict) -> tuple[bool, dict, str | None]:
    """Make a POST call; return (success, data, error_message)."""
    try:
        client = await get_client(service)
        resp = await client.post(path, json=json)
        if resp.status_code in (200, 201):
            return True, resp.json(), None
        return False, {}, f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, {}, str(e)


async def _get(service: str, path: str) -> tuple[bool, dict | list, str | None]:
    try:
        client = await get_client(service)
        resp = await client.get(path)
        if resp.status_code == 200:
            return True, resp.json(), None
        return False, {}, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, {}, str(e)


@router.post("/simulate/happy_path", response_model=SimulationResult)
async def simulate_happy_path(req: SimulateRequest):
    """
    Orchestrates the full order → payment → ERP → inventory → invoice → shipment flow.
    With a failure_mode set, injects the specified failure at the right step so
    Invariant's detection engine has real anomalies to find.
    """
    steps: list[StepResult] = []
    log = logger.bind(failure_mode=req.failure_mode)

    # ── Step 1: Create Order ──────────────────────────────────────────────────
    ok, order_data, err = await _post("order", "/orders", {
        "customer_email": req.customer_email,
        "customer_name":  req.customer_name,
        "items": [{
            "sku":               req.sku,
            "name":              req.product_name,
            "qty":               req.qty,
            "unit_price_paise":  req.unit_price_paise,
        }],
        "notes": {"failure_mode": req.failure_mode},
    })
    if ok:
        transaction_ref = order_data["transaction_ref"]
        order_id        = order_data["id"]
    else:
        transaction_ref = f"TXN-FAIL-{uuid.uuid4().hex[:6].upper()}"

    steps.append(StepResult(step="order_created", success=ok,
                             data=order_data if ok else None, error=err))
    if not ok:
        return SimulationResult(transaction_ref=transaction_ref,
                                failure_mode=req.failure_mode, steps=steps,
                                final_status="FAILED",
                                summary=f"Order creation failed: {err}")

    log = log.bind(transaction_ref=transaction_ref)
    log.info("simulation_started")

    # ── Step 2: Capture Payment ───────────────────────────────────────────────
    # WRONG_AMOUNT failure: classic paise-to-rupee conversion bug
    payment_amount = order_data["total_amount_paise"]
    if req.failure_mode == FailureMode.WRONG_AMOUNT:
        payment_amount = payment_amount // 100   # records ₹600 instead of ₹60,000

    idempotency_key = f"pay-{transaction_ref}"
    ok, payment_data, err = await _post("payment", "/payments/capture", {
        "transaction_ref":  transaction_ref,
        "amount_paise":     payment_amount,
        "currency":         "INR",
        "method":           "upi",
        "idempotency_key":  idempotency_key,
    })
    steps.append(StepResult(step="payment_captured", success=ok,
                             data=payment_data if ok else None, error=err))
    payment_id = payment_data.get("id") if ok else None

    # DUPLICATE_PAYMENT_EVENT: resend identical capture — must be idempotent
    if ok and req.failure_mode == FailureMode.DUPLICATE_PAYMENT_EVENT:
        ok2, dup_data, _ = await _post("payment", "/payments/capture", {
            "transaction_ref":  transaction_ref,
            "amount_paise":     payment_amount,
            "currency":         "INR",
            "method":           "upi",
            "idempotency_key":  idempotency_key,   # Same key → must return same record
        })
        duplicate_ok = ok2 and dup_data.get("id") == payment_id
        steps.append(StepResult(
            step="payment_duplicate_idempotency_check",
            success=duplicate_ok,
            data={"same_id_returned": duplicate_ok, "id": dup_data.get("id")},
            error=None if duplicate_ok else "Duplicate payment created a NEW record — idempotency broken",
        ))

    # ── Step 3: ERP Sales Order ───────────────────────────────────────────────
    # Activate silent-failure mode on ERP if requested
    if req.failure_mode == FailureMode.ERP_SILENT_FAILURE:
        erp_client = await get_client("erp")
        await erp_client.post("/erp/failure", params={"mode": "erp_silent_failure", "active": "true"})

    ok, erp_data, err = await _post("erp", "/erp/orders", {
        "transaction_ref":    transaction_ref,
        "customer_id":        req.customer_email,
        "customer_email":     req.customer_email,
        "line_items":         [{"sku": req.sku, "name": req.product_name,
                                "qty": req.qty, "unit_price_paise": req.unit_price_paise}],
        "total_amount_paise": order_data["total_amount_paise"],
    })

    # Deactivate after use
    if req.failure_mode == FailureMode.ERP_SILENT_FAILURE:
        erp_client = await get_client("erp")
        await erp_client.post("/erp/failure", params={"mode": "erp_silent_failure", "active": "false"})

    # Detect the silent failure: API said 200 but left a sentinel in the response
    is_silent = ok and erp_data.get("note") == "__SIMULATED_SILENT_FAILURE__"
    if is_silent:
        steps.append(StepResult(
            step="erp_order_created", success=False,
            data=erp_data,
            error="SILENT_FAILURE: ERP returned HTTP 200 but persisted no record",
        ))
        return SimulationResult(
            transaction_ref=transaction_ref,
            failure_mode=req.failure_mode, steps=steps,
            final_status="PARTIAL_FAILURE",
            summary=(
                "Silent ERP failure detected: payment captured (money taken) but "
                "ERP has no sales order. Classic distributed inconsistency — "
                "this is exactly what Invariant's reconciliation engine must catch."
            ),
        )

    steps.append(StepResult(step="erp_order_created", success=ok,
                             data=erp_data if ok else None, error=err))
    erp_order_id = erp_data.get("id") if ok else None
    if not ok:
        return SimulationResult(
            transaction_ref=transaction_ref,
            failure_mode=req.failure_mode, steps=steps,
            final_status="PARTIAL_FAILURE",
            summary=f"Partial failure: payment captured but ERP order creation failed — {err}",
        )

    # ── Step 4: Reserve Inventory ─────────────────────────────────────────────
    ok, inv_data, err = await _post("erp", "/erp/inventory/reserve", {
        "transaction_ref":  transaction_ref,
        "sales_order_id":   erp_order_id,
        "items": [{"sku": req.sku, "name": req.product_name,
                   "qty": req.qty, "unit_price_paise": req.unit_price_paise}],
    })
    steps.append(StepResult(step="inventory_reserved", success=ok,
                             data=inv_data if ok else None, error=err))

    # ── Step 5: Generate Invoice ──────────────────────────────────────────────
    ok, inv_resp, err = await _post("erp", "/erp/invoices", {
        "transaction_ref":  transaction_ref,
        "sales_order_id":   erp_order_id,
        "amount_paise":     order_data["total_amount_paise"],
    })
    steps.append(StepResult(step="invoice_generated", success=ok,
                             data=inv_resp if ok else None, error=err))

    # ── Step 6: Create Shipment ───────────────────────────────────────────────
    if req.failure_mode == FailureMode.SHIPMENT_FAILS:
        ship_client = await get_client("shipping")
        await ship_client.post("/shipments/failure",
                               params={"mode": "shipment_creation_fails", "active": "true"})

    ok, ship_data, err = await _post("shipping", "/shipments", {
        "transaction_ref":  transaction_ref,
        "sales_order_id":   erp_order_id,
        "recipient_name":   req.customer_name,
        "recipient_email":  req.customer_email,
        "delivery_address": {
            "line1":   "123 Test Street",
            "city":    "Bengaluru",
            "state":   "Karnataka",
            "pincode": "560001",
        },
        "carrier": "BLUEDART",
    })

    if req.failure_mode == FailureMode.SHIPMENT_FAILS:
        ship_client = await get_client("shipping")
        await ship_client.post("/shipments/failure",
                               params={"mode": "shipment_creation_fails", "active": "false"})

    steps.append(StepResult(step="shipment_created", success=ok,
                             data=ship_data if ok else None, error=err))

    # ── Final result ──────────────────────────────────────────────────────────
    all_ok        = all(s.success for s in steps)
    failed_steps  = [s.step for s in steps if not s.success]
    final_status  = "COMPLETED" if all_ok else "PARTIAL_FAILURE"
    summary = (
        "All 6 steps completed successfully — transaction fully consistent."
        if all_ok else
        f"Partial failure at step(s): {failed_steps}. "
        "Transaction left in inconsistent state — Invariant should detect this."
    )
    log.info("simulation_finished", final_status=final_status, failed_steps=failed_steps)
    return SimulationResult(
        transaction_ref=transaction_ref,
        failure_mode=req.failure_mode,
        steps=steps,
        final_status=final_status,
        summary=summary,
    )


@router.get("/simulate/status/{transaction_ref}")
async def get_transaction_status(transaction_ref: str):
    """
    Queries all four services for the CURRENT state of a transaction.
    Returns a cross-system view — the cornerstone of what Invariant validates.
    """
    results = {}
    queries = [
        ("order",    f"/orders/{transaction_ref}"),
        ("payment",  f"/payments?transaction_ref={transaction_ref}"),
        ("erp",      f"/erp/orders/{transaction_ref}"),
        ("shipping", f"/shipments/{transaction_ref}"),
    ]
    for service, path in queries:
        ok, data, err = await _get(service, path)
        results[service] = {"found": ok, "data": data if ok else None, "error": err}

    # Quick consistency check: highlight obvious mismatches
    issues = []
    if results["order"]["found"] and not results["erp"]["found"]:
        issues.append("ORDER exists but ERP has no sales order — potential inconsistency")
    if results["payment"]["found"] and not results["order"]["found"]:
        issues.append("PAYMENT exists but ORDER missing — orphan payment")
    if results["shipping"]["found"] and not results["erp"]["found"]:
        issues.append("SHIPMENT created but no ERP order — fulfillment without sales record")

    return {
        "transaction_ref": transaction_ref,
        "services":        results,
        "consistency_issues": issues,
        "is_consistent": len(issues) == 0,
    }


@router.get("/simulate/scenarios")
async def list_scenarios():
    """Lists all injectable failure scenarios with descriptions."""
    return {
        "scenarios": [
            {
                "mode":        "none",
                "name":        "Happy Path",
                "description": "Full end-to-end success. All 6 steps complete. No inconsistency.",
                "systems_affected": ["all"],
            },
            {
                "mode":        "erp_silent_failure",
                "name":        "ERP Silent Failure",
                "description": "ERP API returns HTTP 200 but persists no record. "
                               "Payment is captured, money is taken, but ERP has no order. "
                               "Classic silent data inconsistency — cannot be detected by HTTP monitoring alone.",
                "systems_affected": ["erp"],
                "invariant_violated": "payment_without_erp_order",
            },
            {
                "mode":        "wrong_amount",
                "name":        "Amount Mismatch (Paise/Rupee Bug)",
                "description": "Payment captured for 1/100th of the order amount. "
                               "Simulates a paise-to-rupee conversion bug in the payment integration.",
                "systems_affected": ["payment"],
                "invariant_violated": "amount_consistency",
            },
            {
                "mode":        "shipment_creation_fails",
                "name":        "Shipment Creation Failure",
                "description": "Shipping provider returns 503. Order paid and ERP updated, "
                               "but shipment never created. Transaction stuck in PARTIAL_FAILURE.",
                "systems_affected": ["shipping"],
                "invariant_violated": "fulfillment_completeness",
            },
            {
                "mode":        "duplicate_payment_event",
                "name":        "Duplicate Payment Event",
                "description": "Same payment capture request sent twice with identical idempotency key. "
                               "Payment service must return the same record, not create two payments.",
                "systems_affected": ["payment"],
                "invariant_violated": "no_duplicate_payments",
            },
        ]
    }

