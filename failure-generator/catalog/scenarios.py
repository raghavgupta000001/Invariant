"""
Invariant Failure Scenario Catalog
===================================
50 reproducible failure scenarios, each with:
  - id              : unique slug
  - category        : failure class
  - name            : human-readable label
  - description     : what happens
  - simulate_params : dict passed to POST /simulate/happy_path
  - ground_truth    : expected detection result
    - incident_type         : what Invariant's engine should raise
    - invariant_violated    : which invariant SQL check catches it
    - detection_method      : "event_driven" | "scheduled_reconciliation" | "both"
    - first_divergence_step : where the workflow first diverges
    - root_cause            : ground-truth root cause string (for RCA eval)
    - expected_recovery     : what saga compensation applies
  - severity        : CRITICAL | HIGH | MEDIUM | LOW
  - tags            : searchable labels
"""

from dataclasses import dataclass, field, asdict
from typing import Literal


@dataclass
class GroundTruth:
    incident_type: str
    invariant_violated: str
    detection_method: Literal["event_driven", "scheduled_reconciliation", "both"]
    first_divergence_step: str
    root_cause: str
    expected_recovery: str


@dataclass
class FailureScenario:
    id: str
    category: str
    name: str
    description: str
    simulate_params: dict
    ground_truth: GroundTruth
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY A: Silent Failures (API says OK, state is wrong)
# ─────────────────────────────────────────────────────────────────────────────

SCENARIOS: list[FailureScenario] = [

    FailureScenario(
        id="F001",
        category="silent_failure",
        name="ERP Silent Failure — Order Not Persisted",
        description=(
            "ERP API returns HTTP 200 OK but rolls back its DB transaction internally. "
            "Payment is captured, money deducted, but ERP has no sales order record. "
            "Cannot be detected by HTTP status monitoring alone."
        ),
        simulate_params={"failure_mode": "erp_silent_failure"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP",
            invariant_violated="payment_without_erp_order",
            detection_method="scheduled_reconciliation",
            first_divergence_step="erp_order_created",
            root_cause=(
                "ERP service returned HTTP 200 but its internal DB transaction was rolled back. "
                "Payment captured (step 2) exists in payments_db but no corresponding record "
                "exists in erp_db.sales_orders for transaction_ref."
            ),
            expected_recovery=(
                "Verify ERP for existing order → Retry order creation with idempotency key → "
                "Confirm exactly one ERP record → Mark transaction reconciled"
            ),
        ),
        severity="CRITICAL",
        tags=["silent", "erp", "reconciliation", "distributed-consistency"],
    ),

    FailureScenario(
        id="F002",
        category="silent_failure",
        name="Inventory Quantity Mismatch — Partial Reservation",
        description=(
            "ERP reserves inventory for 1 unit but order contains 2 units. "
            "API returns 201, partial hold recorded. Customer paid for 2, only 1 reserved."
        ),
        simulate_params={"failure_mode": "none", "qty": 2},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH",
            invariant_violated="inventory_quantity_matches_order",
            detection_method="scheduled_reconciliation",
            first_divergence_step="inventory_reserved",
            root_cause=(
                "Inventory reservation hold qty (1) does not match order line item qty (2). "
                "Caused by an off-by-one error in the ERP connector's qty mapping."
            ),
            expected_recovery=(
                "Release existing partial hold → Reserve correct quantity → Verify hold qty matches order"
            ),
        ),
        severity="HIGH",
        tags=["silent", "inventory", "data-mismatch"],
    ),

    FailureScenario(
        id="F003",
        category="silent_failure",
        name="Invoice Amount Wrong — ₹60,000 Invoiced as ₹600",
        description=(
            "Invoice generated with amount_paise = order_amount / 100. "
            "Classic paise-to-rupee conversion error. API succeeds, number is wrong."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH",
            invariant_violated="invoice_amount_matches_payment",
            detection_method="scheduled_reconciliation",
            first_divergence_step="invoice_generated",
            root_cause=(
                "Invoice connector divides amount_paise by 100 before sending to ERP, "
                "but ERP stores the value as-is assuming paise. Result: invoice records "
                "1/100th of the correct amount."
            ),
            expected_recovery="Void incorrect invoice → Regenerate invoice with correct amount → Verify",
        ),
        severity="CRITICAL",
        tags=["silent", "invoice", "amount", "currency-bug"],
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY B: Webhook / Event Delivery Failures
    # ─────────────────────────────────────────────────────────────────────────

    FailureScenario(
        id="F004",
        category="webhook_failure",
        name="ERP Webhook Dropped — Event Never Delivered",
        description=(
            "ERP publishes to Pub/Sub but the message is lost (emulated by not publishing). "
            "Invariant's event-driven path never sees the erp.order_created event. "
            "Only the scheduled reconciliation sweep can detect this."
        ),
        simulate_params={"failure_mode": "drop_erp_webhook"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP",
            invariant_violated="payment_without_erp_order",
            detection_method="scheduled_reconciliation",
            first_divergence_step="erp_order_created",
            root_cause=(
                "Pub/Sub publish call timed out or dropped. ERP record was created in erp_db "
                "but the erp.order_created event was never delivered to Invariant's ingestion layer."
            ),
            expected_recovery="Backfill event from ERP API poll → Mark step as COMPLETED → Continue workflow",
        ),
        severity="HIGH",
        tags=["webhook", "pubsub", "event-loss", "erp"],
    ),

    FailureScenario(
        id="F005",
        category="webhook_failure",
        name="Duplicate Payment Event — At-Least-Once Delivery",
        description=(
            "Payment gateway retries the payment.captured webhook. "
            "Second delivery must be idempotent — no second payment record created."
        ),
        simulate_params={"failure_mode": "duplicate_payment_event"},
        ground_truth=GroundTruth(
            incident_type="DUPLICATE_EVENT",
            invariant_violated="no_duplicate_payments",
            detection_method="event_driven",
            first_divergence_step="payment_captured",
            root_cause=(
                "Razorpay at-least-once delivery sent the same payment.captured event twice. "
                "If idempotency_key deduplication is not implemented, two payment records "
                "are created for the same transaction."
            ),
            expected_recovery="Verify only one payment record exists → Delete orphan → Mark reconciled",
        ),
        severity="HIGH",
        tags=["webhook", "duplicate", "idempotency", "payment"],
    ),

    FailureScenario(
        id="F006",
        category="webhook_failure",
        name="Out-of-Order Events — Shipment Before Payment",
        description=(
            "shipment.created event arrives before payment.captured due to clock skew. "
            "State machine sees fulfillment step before payment step — invalid ordering."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORDERING_VIOLATION",
            invariant_violated="no_shipment_without_payment",
            detection_method="event_driven",
            first_divergence_step="shipment_created",
            root_cause=(
                "Clock skew between payment-service and shipping-service caused occurred_at "
                "timestamps to be inverted. shipment.created.occurred_at < payment.captured.occurred_at "
                "even though shipment was processed after payment."
            ),
            expected_recovery="Reorder events by occurred_at → Re-evaluate state machine → No data change needed",
        ),
        severity="MEDIUM",
        tags=["webhook", "ordering", "clock-skew", "event-sourcing"],
    ),

    FailureScenario(
        id="F007",
        category="webhook_failure",
        name="Corrupted Webhook Signature",
        description=(
            "Webhook arrives with an invalid HMAC-SHA256 signature. "
            "Should be rejected at the ingestion layer without poisoning the event log."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SILENT_FAILURE",
            invariant_violated="all_events_signature_verified",
            detection_method="event_driven",
            first_divergence_step="payment_captured",
            root_cause=(
                "Webhook secret rotation was not synchronized between Razorpay dashboard "
                "and Invariant's Secret Manager secret. Old signature computed with old key."
            ),
            expected_recovery="Rotate webhook secret → Re-register endpoint → Replay missed events from API",
        ),
        severity="HIGH",
        tags=["webhook", "security", "hmac", "signature"],
    ),

    FailureScenario(
        id="F008",
        category="webhook_failure",
        name="Delayed Webhook — 4 Hours Late",
        description=(
            "Payment webhook arrives 4 hours after the event occurred. "
            "Transaction is already flagged as SLA-breached. "
            "Late event must be processed correctly without re-triggering false incidents."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SLA_BREACH",
            invariant_violated="sla_breach_detection",
            detection_method="both",
            first_divergence_step="payment_captured",
            root_cause=(
                "Receiving server was down during Shopify's 8-retry window. "
                "Final retry succeeded 4 hours later. occurred_at vs ingested_at delta = 4h."
            ),
            expected_recovery="Process late event → Backdate step completion → Close SLA breach incident",
        ),
        severity="MEDIUM",
        tags=["webhook", "delay", "sla", "retry"],
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY C: Data Mismatches
    # ─────────────────────────────────────────────────────────────────────────

    FailureScenario(
        id="F009",
        category="data_mismatch",
        name="Amount Mismatch — Paise/Rupee Bug",
        description=(
            "Payment captured for ₹600 (60,000 paise) instead of ₹60,000 (6,000,000 paise). "
            "Classic integer division error in currency unit conversion."
        ),
        simulate_params={"failure_mode": "wrong_amount"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH",
            invariant_violated="amount_consistency",
            detection_method="scheduled_reconciliation",
            first_divergence_step="payment_captured",
            root_cause=(
                "Payment connector divided amount_paise by 100 before sending to Razorpay, "
                "treating paise as rupees. Order total = 6,000,000 paise; "
                "payment captured = 60,000 paise. Delta = 5,940,000 paise (₹59,400)."
            ),
            expected_recovery=(
                "Initiate refund for wrong amount → Capture correct amount → "
                "Verify payment = order amount → Update ERP invoice"
            ),
        ),
        severity="CRITICAL",
        tags=["data-mismatch", "amount", "currency", "payment"],
    ),

    FailureScenario(
        id="F010",
        category="data_mismatch",
        name="Wrong Customer ID in ERP Order",
        description=(
            "ERP sales order created with customer_id = None (null) because the "
            "field mapping from order service to ERP connector was broken."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH",
            invariant_violated="erp_order_customer_id_present",
            detection_method="scheduled_reconciliation",
            first_divergence_step="erp_order_created",
            root_cause=(
                "ERP connector maps order.customer_email → erp.customer_id but the "
                "field was renamed from 'email' to 'customer_email' in the order schema v2 update. "
                "Connector was not updated — sends null customer_id."
            ),
            expected_recovery="Update field mapping → Patch ERP order with correct customer_id → Verify",
        ),
        severity="HIGH",
        tags=["data-mismatch", "schema-drift", "erp", "field-mapping"],
    ),

    FailureScenario(
        id="F011",
        category="data_mismatch",
        name="Currency Mismatch — USD vs INR",
        description=(
            "Order placed in INR but payment gateway processes in USD. "
            "Amounts appear matching in numbers but currency codes differ."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH",
            invariant_violated="currency_consistency",
            detection_method="scheduled_reconciliation",
            first_divergence_step="payment_captured",
            root_cause=(
                "Payment connector hardcoded currency='USD' instead of reading from "
                "the order's currency field. Numerical amounts match but currencies differ."
            ),
            expected_recovery="Refund USD payment → Capture correct INR payment → Update payment record",
        ),
        severity="CRITICAL",
        tags=["data-mismatch", "currency", "payment"],
    ),

    FailureScenario(
        id="F012",
        category="data_mismatch",
        name="SKU Mismatch — Wrong Product in ERP",
        description=(
            "Order contains SKU 'LAPTOP-PRO-15' but ERP order records 'LAPTOP-STD-15'. "
            "Wrong product will be picked from warehouse."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH",
            invariant_violated="sku_consistency",
            detection_method="scheduled_reconciliation",
            first_divergence_step="erp_order_created",
            root_cause=(
                "ERP connector applies a SKU normalizer that maps 'PRO' → 'STD' "
                "for a discontinued product line. Mapping table was not updated after launch."
            ),
            expected_recovery="Cancel ERP order → Re-create with correct SKU → Verify inventory for correct SKU",
        ),
        severity="HIGH",
        tags=["data-mismatch", "sku", "erp", "inventory"],
    ),

    FailureScenario(
        id="F013",
        category="data_mismatch",
        name="Shipping Address Truncated",
        description=(
            "Delivery address line1 is truncated to 50 chars by shipping connector. "
            "Full address does not fit — parcel undeliverable."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH",
            invariant_violated="address_completeness",
            detection_method="scheduled_reconciliation",
            first_divergence_step="shipment_created",
            root_cause=(
                "Shipping connector VARCHAR(50) limit on address field silently truncates "
                "longer addresses. No validation error raised — data silently corrupted."
            ),
            expected_recovery="Update shipment address in carrier system → Verify full address stored",
        ),
        severity="MEDIUM",
        tags=["data-mismatch", "shipping", "address", "truncation"],
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY D: Partial Failures (some steps done, later steps failed)
    # ─────────────────────────────────────────────────────────────────────────

    FailureScenario(
        id="F014",
        category="partial_failure",
        name="Shipment Service Down — Steps 1-5 OK, Step 6 Fails",
        description=(
            "Shipping service returns 503. Order paid, ERP updated, invoice generated. "
            "No shipment. Customer sees money deducted but no tracking number."
        ),
        simulate_params={"failure_mode": "shipment_creation_fails"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP",
            invariant_violated="fulfillment_completeness",
            detection_method="event_driven",
            first_divergence_step="shipment_created",
            root_cause=(
                "Shipping service was OOM-killed during deployment. "
                "Steps 1-5 persisted successfully. Step 6 failed with HTTP 503."
            ),
            expected_recovery="Retry shipment creation → Verify exactly one shipment per transaction → Send tracking to customer",
        ),
        severity="HIGH",
        tags=["partial-failure", "shipping", "503", "saga"],
    ),

    FailureScenario(
        id="F015",
        category="partial_failure",
        name="Invoice Service Timeout — Steps 1-4 OK, Step 5 Fails",
        description=(
            "Invoice generation times out. Inventory reserved, payment captured, "
            "but no invoice exists. Financial records incomplete."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP",
            invariant_violated="invoice_exists_for_payment",
            detection_method="event_driven",
            first_divergence_step="invoice_generated",
            root_cause=(
                "ERP invoice generation endpoint timed out after 30s. "
                "DB row may or may not have been committed — requires idempotency check before retry."
            ),
            expected_recovery=(
                "Check ERP for existing invoice → If none: retry → "
                "If exists: mark step complete → Verify amount"
            ),
        ),
        severity="HIGH",
        tags=["partial-failure", "invoice", "timeout", "saga"],
    ),

    FailureScenario(
        id="F016",
        category="partial_failure",
        name="ERP Order Fails After Payment — Compensation Required",
        description=(
            "Payment captured successfully but ERP order creation returns 500. "
            "Must initiate refund (compensating transaction) to restore consistent state."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP",
            invariant_violated="payment_without_erp_order",
            detection_method="event_driven",
            first_divergence_step="erp_order_created",
            root_cause=(
                "ERP service returned HTTP 500 — internal server error. "
                "Payment is captured, money is taken. Business decision: "
                "cannot proceed without ERP order → must refund."
            ),
            expected_recovery=(
                "Initiate payment refund (compensating transaction) → "
                "Cancel order → Notify customer → Close incident"
            ),
        ),
        severity="CRITICAL",
        tags=["partial-failure", "erp", "compensation", "saga", "refund"],
    ),

    FailureScenario(
        id="F017",
        category="partial_failure",
        name="Double Shipment — Idempotency Key Missing on Retry",
        description=(
            "Shipping step times out, retry is issued without idempotency key. "
            "Two shipments created for one order."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DUPLICATE_EVENT",
            invariant_violated="one_shipment_per_transaction",
            detection_method="event_driven",
            first_divergence_step="shipment_created",
            root_cause=(
                "Recovery executor did not check idempotency before retrying shipment creation. "
                "Original request succeeded (timed out on response). Retry created a second shipment."
            ),
            expected_recovery=(
                "Identify duplicate shipment → Cancel one → Notify carrier → "
                "Mark original as canonical shipment"
            ),
        ),
        severity="HIGH",
        tags=["partial-failure", "duplicate", "idempotency", "shipping", "retry"],
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY E: SLA / Stuck Transactions
    # ─────────────────────────────────────────────────────────────────────────

    FailureScenario(
        id="F018",
        category="sla_breach",
        name="Transaction Stuck in IN_PROGRESS for 2 Hours",
        description=(
            "Order created and payment captured but no subsequent events received. "
            "Transaction stuck — SLA of 60 minutes breached."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SLA_BREACH",
            invariant_violated="sla_breach_detection",
            detection_method="scheduled_reconciliation",
            first_divergence_step="erp_order_created",
            root_cause=(
                "ERP connector queue backed up — messages queued but not processed. "
                "No events published for 2h. Scheduled reconciliation sweep detects "
                "transactions where expected_completion_at < NOW()."
            ),
            expected_recovery="Escalate to ops team → Drain ERP connector queue → Replay missed events",
        ),
        severity="HIGH",
        tags=["sla", "stuck", "timeout", "queue-backup"],
    ),

    FailureScenario(
        id="F019",
        category="sla_breach",
        name="Inventory Reservation Pending for 30 Minutes",
        description=(
            "ERP order created but inventory hold never recorded. "
            "Could indicate stock exhaustion or ERP batch job delay."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SLA_BREACH",
            invariant_violated="sla_breach_detection",
            detection_method="scheduled_reconciliation",
            first_divergence_step="inventory_reserved",
            root_cause=(
                "ERP inventory reservation is processed by a batch job that runs every 15 minutes. "
                "Job failed in one cycle — reservation delayed by 30+ minutes."
            ),
            expected_recovery="Trigger manual inventory reservation → Verify hold exists → Continue workflow",
        ),
        severity="MEDIUM",
        tags=["sla", "inventory", "batch-job"],
    ),

    FailureScenario(
        id="F020",
        category="sla_breach",
        name="Payment Pending for 10 Minutes — Gateway Timeout",
        description=(
            "Order created but payment gateway did not respond within SLA. "
            "Customer may retry, risking duplicate payment."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SLA_BREACH",
            invariant_violated="sla_breach_detection",
            detection_method="scheduled_reconciliation",
            first_divergence_step="payment_captured",
            root_cause=(
                "Razorpay API gateway returned 504 during peak traffic. "
                "Payment state unknown — may be CAPTURED or FAILED in gateway."
            ),
            expected_recovery=(
                "Query Razorpay API for payment status → "
                "If CAPTURED: record and continue → If FAILED: allow retry → "
                "If PENDING: wait with timeout"
            ),
        ),
        severity="HIGH",
        tags=["sla", "payment", "gateway-timeout"],
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY F: Orphan Records
    # ─────────────────────────────────────────────────────────────────────────

    FailureScenario(
        id="F021",
        category="orphan_record",
        name="Payment Without Order — Customer Paid After Order Cancelled",
        description=(
            "Order was cancelled but payment was captured anyway. "
            "Payment exists in payments_db with no live order. Money taken for cancelled order."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORPHAN_RECORD",
            invariant_violated="no_payment_for_cancelled_order",
            detection_method="event_driven",
            first_divergence_step="payment_captured",
            root_cause=(
                "Race condition: order.cancelled event processed after payment.captured. "
                "Payment gateway did not check order status before capture."
            ),
            expected_recovery="Initiate automatic refund for orphan payment → Notify customer",
        ),
        severity="CRITICAL",
        tags=["orphan", "payment", "race-condition", "cancellation"],
    ),

    FailureScenario(
        id="F022",
        category="orphan_record",
        name="ERP Order Without Payment",
        description=(
            "ERP has a sales order but no payment exists. "
            "Could indicate a free order or a webhook ordering issue."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORPHAN_RECORD",
            invariant_violated="erp_order_has_payment",
            detection_method="scheduled_reconciliation",
            first_divergence_step="payment_captured",
            root_cause=(
                "payment.captured webhook was lost. ERP order was created by a "
                "background reconciliation job before the payment was confirmed."
            ),
            expected_recovery=(
                "Query payment gateway for actual payment status → "
                "If captured: backfill payment record → If not: cancel ERP order"
            ),
        ),
        severity="HIGH",
        tags=["orphan", "erp", "payment", "reconciliation"],
    ),

    FailureScenario(
        id="F023",
        category="orphan_record",
        name="Shipment Without ERP Order",
        description=(
            "Shipment created but no ERP sales order found. "
            "Goods shipped without financial record — revenue leakage."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORPHAN_RECORD",
            invariant_violated="no_shipment_without_erp_order",
            detection_method="both",
            first_divergence_step="erp_order_created",
            root_cause=(
                "ERP API was temporarily down. Shipping service was triggered by a "
                "direct webhook from Shopify bypassing the ERP step in the workflow."
            ),
            expected_recovery="Create ERP order retroactively → Link shipment to order → Audit financial records",
        ),
        severity="HIGH",
        tags=["orphan", "shipment", "erp", "revenue-leakage"],
    ),

    FailureScenario(
        id="F024",
        category="orphan_record",
        name="Refund Without Original Payment",
        description=(
            "Refund record exists in payments_db but the original payment cannot be found. "
            "Potential fraud or data corruption."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORPHAN_RECORD",
            invariant_violated="refund_has_parent_payment",
            detection_method="scheduled_reconciliation",
            first_divergence_step="payment_captured",
            root_cause=(
                "Original payment record was deleted (data retention policy applied incorrectly). "
                "Refund record remains as an orphan."
            ),
            expected_recovery="Restore payment record from audit log → Re-link refund → Alert security team",
        ),
        severity="CRITICAL",
        tags=["orphan", "refund", "fraud", "data-integrity"],
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY G: Schema Drift
    # ─────────────────────────────────────────────────────────────────────────

    FailureScenario(
        id="F025",
        category="schema_drift",
        name="ERP API Renamed customer_id → client_id",
        description=(
            "ERP upgraded their API. customer_id field renamed to client_id. "
            "Connector sends customer_id which is now ignored — ERP stores null."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SCHEMA_DRIFT",
            invariant_violated="erp_order_customer_id_present",
            detection_method="scheduled_reconciliation",
            first_divergence_step="erp_order_created",
            root_cause=(
                "ERP v2 API renamed customer_id to client_id without a deprecation period. "
                "Invariant detected this by comparing ERP order records against expected schema: "
                "erp_db.sales_orders.customer_id IS NULL for all orders after the ERP upgrade date."
            ),
            expected_recovery="Update field mapping in connector → Backfill customer_id for affected orders",
        ),
        severity="HIGH",
        tags=["schema-drift", "erp", "field-rename", "api-version"],
    ),

    FailureScenario(
        id="F026",
        category="schema_drift",
        name="Shipping Webhook Added Required Field",
        description=(
            "Shipping provider added a required 'weight_grams' field to shipment creation. "
            "Existing connector doesn't send it — shipments silently not created."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SCHEMA_DRIFT",
            invariant_violated="fulfillment_completeness",
            detection_method="event_driven",
            first_divergence_step="shipment_created",
            root_cause=(
                "Shipping provider v3 API made weight_grams required. "
                "Connector sends no weight, provider silently skips shipment creation. "
                "API still returns 200 — another silent failure."
            ),
            expected_recovery="Update connector with weight_grams → Retry failed shipments",
        ),
        severity="HIGH",
        tags=["schema-drift", "shipping", "required-field", "api-version"],
    ),

    FailureScenario(
        id="F027",
        category="schema_drift",
        name="Payment Webhook Event Type Changed",
        description=(
            "Payment gateway changed event type from 'payment.captured' to 'payment.success'. "
            "Normalizer doesn't recognize new type — events go to dead-letter queue."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SCHEMA_DRIFT",
            invariant_violated="all_events_normalized",
            detection_method="event_driven",
            first_divergence_step="payment_captured",
            root_cause=(
                "Razorpay renamed event type in their v2 webhook spec. "
                "Normalizer's EVENT_TYPE_MAP does not contain 'payment.success' — "
                "returns NormalizationResult.unrecognized() → event dead-lettered."
            ),
            expected_recovery="Update normalizer EVENT_TYPE_MAP → Replay dead-lettered events",
        ),
        severity="HIGH",
        tags=["schema-drift", "payment", "event-type", "dead-letter"],
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY H: Duplicate / Idempotency Violations
    # ─────────────────────────────────────────────────────────────────────────

    FailureScenario(
        id="F028",
        category="duplicate",
        name="Same Order Processed Twice",
        description=(
            "Shopify retries the order.created webhook. Order service creates two orders "
            "for the same transaction if idempotency is not enforced."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DUPLICATE_EVENT",
            invariant_violated="one_order_per_transaction_ref",
            detection_method="event_driven",
            first_divergence_step="order_created",
            root_cause=(
                "Shopify 8-retry policy fired a second delivery. Order service "
                "did not check for existing order by transaction_ref before INSERT."
            ),
            expected_recovery="Delete duplicate order → Keep the original → Verify downstream refs point to correct order",
        ),
        severity="HIGH",
        tags=["duplicate", "order", "idempotency", "shopify-retry"],
    ),

    FailureScenario(
        id="F029",
        category="duplicate",
        name="Double Invoice — ERP Job Ran Twice",
        description=(
            "Invoice generation job triggered twice due to a scheduler bug. "
            "Two invoices exist for one transaction — accounting error."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DUPLICATE_EVENT",
            invariant_violated="one_invoice_per_transaction",
            detection_method="scheduled_reconciliation",
            first_divergence_step="invoice_generated",
            root_cause=(
                "Cloud Scheduler had a duplicate trigger due to a daylight saving time transition. "
                "Invoice job ran twice within 1 minute. No idempotency check in invoice endpoint."
            ),
            expected_recovery="Void duplicate invoice → Verify one canonical invoice remains → Fix scheduler",
        ),
        severity="HIGH",
        tags=["duplicate", "invoice", "scheduler-bug", "idempotency"],
    ),

    FailureScenario(
        id="F030",
        category="duplicate",
        name="Double Refund — Retry Without Idempotency Key",
        description=(
            "Customer support initiated a refund, it timed out, and they retried without an idempotency key. "
            "Customer refunded twice — financial loss for the business."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DUPLICATE_EVENT",
            invariant_violated="one_refund_per_payment",
            detection_method="event_driven",
            first_divergence_step="payment_captured",
            root_cause=(
                "Refund API called twice without idempotency_key. "
                "Second call not deduplicated — created a second refund record."
            ),
            expected_recovery="Identify second refund → Reverse it via contra-credit → Alert finance team",
        ),
        severity="CRITICAL",
        tags=["duplicate", "refund", "idempotency", "financial-loss"],
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY I: Infrastructure / Network Failures
    # ─────────────────────────────────────────────────────────────────────────

    FailureScenario(
        id="F031",
        category="infrastructure",
        name="Database Connection Pool Exhausted",
        description=(
            "Order service's asyncpg pool hits max_size=10 during traffic spike. "
            "New requests fail with connection timeout — orders not created."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP",
            invariant_violated="sla_breach_detection",
            detection_method="event_driven",
            first_divergence_step="order_created",
            root_cause="asyncpg connection pool exhausted. max_size=10 insufficient for traffic spike.",
            expected_recovery="Scale pool size → Drain queue → Retry failed order creations",
        ),
        severity="HIGH",
        tags=["infrastructure", "database", "connection-pool", "scaling"],
    ),

    FailureScenario(
        id="F032",
        category="infrastructure",
        name="Pub/Sub Emulator Restart — Messages Lost",
        description=(
            "Local Pub/Sub emulator restarted mid-transaction. "
            "Unpublished messages in-flight are lost. Events never reach Invariant."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP",
            invariant_violated="payment_without_erp_order",
            detection_method="scheduled_reconciliation",
            first_divergence_step="erp_order_created",
            root_cause=(
                "Pub/Sub emulator process killed during deployment. "
                "In-flight messages were not persisted. "
                "Services with outbox pattern can replay; those without cannot."
            ),
            expected_recovery="Poll source APIs for missed events → Replay from service logs → Backfill event log",
        ),
        severity="HIGH",
        tags=["infrastructure", "pubsub", "message-loss", "restart"],
    ),

    FailureScenario(
        id="F033",
        category="infrastructure",
        name="Network Partition — ERP Unreachable for 5 Minutes",
        description=(
            "Network partition isolates ERP service. All calls fail with connection refused. "
            "5 transactions reach payment step but cannot proceed."
        ),
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP",
            invariant_violated="sla_breach_detection",
            detection_method="both",
            first_divergence_step="erp_order_created",
            root_cause="Network partition: ERP service unreachable. All TCP connections refused for 5 minutes.",
            expected_recovery="Wait for partition to heal → Retry queued ERP operations with idempotency → Verify no duplicates",
        ),
        severity="CRITICAL",
        tags=["infrastructure", "network-partition", "erp", "availability"],
    ),

    # Extend with 17 more concise scenarios to reach 50 total

    FailureScenario(id="F034", category="data_mismatch", name="Phone Number Format Mismatch",
        description="Order has +91-98765-43210 but ERP expects 9876543210 (no country code, no dashes).",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH", invariant_violated="contact_format_consistency",
            detection_method="scheduled_reconciliation", first_divergence_step="erp_order_created",
            root_cause="Phone number normalizer not applied before ERP connector call.",
            expected_recovery="Patch ERP order with normalized phone → Verify format",
        ), severity="LOW", tags=["data-mismatch", "phone", "normalization"]),

    FailureScenario(id="F035", category="duplicate", name="Inventory Hold Created Twice",
        description="Two inventory_holds rows for same transaction_ref + sku due to retry without idempotency.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DUPLICATE_EVENT", invariant_violated="one_inventory_hold_per_sku_per_transaction",
            detection_method="scheduled_reconciliation", first_divergence_step="inventory_reserved",
            root_cause="Reserve inventory endpoint has no idempotency check on (transaction_ref, sku).",
            expected_recovery="Delete duplicate hold → Verify stock count correct → Mark reconciled",
        ), severity="MEDIUM", tags=["duplicate", "inventory", "idempotency"]),

    FailureScenario(id="F036", category="partial_failure", name="Payment Succeeded, Order Rollback",
        description="Order service crashed mid-INSERT. Payment captured but order row not committed.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORPHAN_RECORD", invariant_violated="payment_without_erp_order",
            detection_method="both", first_divergence_step="order_created",
            root_cause="Order service crashed between DB INSERT and Pub/Sub publish. Transaction rolled back.",
            expected_recovery="Initiate refund → Notify customer to retry order",
        ), severity="CRITICAL", tags=["partial-failure", "crash", "atomicity"]),

    FailureScenario(id="F037", category="schema_drift", name="Decimal Precision Change — 2dp to 4dp",
        description="ERP changed amount storage from 2dp to 4dp. Comparisons fail due to rounding.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SCHEMA_DRIFT", invariant_violated="amount_consistency",
            detection_method="scheduled_reconciliation", first_divergence_step="invoice_generated",
            root_cause="ERP migrated NUMERIC(10,2) to NUMERIC(14,4). Comparison with BIGINT paise now mismatches.",
            expected_recovery="Update reconciliation tolerance → Adjust connector amount serialization",
        ), severity="LOW", tags=["schema-drift", "decimal", "precision"]),

    FailureScenario(id="F038", category="sla_breach", name="Shipment SLA — Not Dispatched in 24h",
        description="Shipment created 24h ago but carrier hasn't picked it up. SLA breached.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SLA_BREACH", invariant_violated="sla_breach_detection",
            detection_method="scheduled_reconciliation", first_divergence_step="shipment_created",
            root_cause="Carrier pickup scheduled for the wrong date due to timezone mismatch in estimated_delivery.",
            expected_recovery="Escalate to carrier → Rebook pickup → Update estimated delivery",
        ), severity="MEDIUM", tags=["sla", "shipping", "pickup"]),

    FailureScenario(id="F039", category="orphan_record", name="Invoice For Non-Existent Order",
        description="Invoice exists in ERP but the linked sales_order_id FK points to a deleted order.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORPHAN_RECORD", invariant_violated="invoice_has_parent_order",
            detection_method="scheduled_reconciliation", first_divergence_step="invoice_generated",
            root_cause="Data retention job deleted test orders but left their invoices.",
            expected_recovery="Void orphan invoice → Archive it → Fix retention policy to cascade",
        ), severity="HIGH", tags=["orphan", "invoice", "data-retention"]),

    FailureScenario(id="F040", category="webhook_failure", name="Webhook Delivered to Wrong Tenant",
        description="Multi-tenant setup: Shopify webhook delivered to Tenant B's endpoint instead of Tenant A.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORPHAN_RECORD", invariant_violated="event_tenant_matches_transaction",
            detection_method="event_driven", first_divergence_step="order_created",
            root_cause="Webhook routing misconfiguration after adding new tenant. URL mapping table stale.",
            expected_recovery="Move event to correct tenant → Reprocess → Fix routing table",
        ), severity="HIGH", tags=["webhook", "multi-tenant", "routing"]),

    FailureScenario(id="F041", category="infrastructure", name="Clock Skew — 5-Minute Drift",
        description="Shipping service NTP drift causes occurred_at to be 5 minutes in the future.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORDERING_VIOLATION", invariant_violated="event_timestamps_monotonic",
            detection_method="event_driven", first_divergence_step="shipment_created",
            root_cause="NTP sync failure on shipping-service host. System clock drifted +5 minutes.",
            expected_recovery="Fix NTP → Normalize timestamps → Re-evaluate event ordering",
        ), severity="LOW", tags=["infrastructure", "clock-skew", "ntp"]),

    FailureScenario(id="F042", category="data_mismatch", name="Recipient Email Mismatch",
        description="Shipment uses billing email, not delivery email. Tracking sent to wrong person.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH", invariant_violated="recipient_email_consistency",
            detection_method="scheduled_reconciliation", first_divergence_step="shipment_created",
            root_cause="Shipping connector reads customer_email from order but should use delivery_email from address.",
            expected_recovery="Update shipment recipient email → Resend tracking notification",
        ), severity="LOW", tags=["data-mismatch", "email", "shipping"]),

    FailureScenario(id="F043", category="partial_failure", name="Inventory Reservation After Cancellation",
        description="Race condition: inventory reserved after order was cancelled. Stock locked for ghost order.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORDERING_VIOLATION", invariant_violated="no_inventory_hold_for_cancelled_order",
            detection_method="event_driven", first_divergence_step="inventory_reserved",
            root_cause="order.cancelled event processed after ERP inventory job started. No cancellation check in job.",
            expected_recovery="Release inventory hold → Mark hold as RELEASED → Reconcile stock count",
        ), severity="HIGH", tags=["partial-failure", "inventory", "race-condition", "cancellation"]),

    FailureScenario(id="F044", category="duplicate", name="Transaction Ref Collision",
        description="Two different customers get the same transaction_ref due to UUID hex truncation collision.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DUPLICATE_EVENT", invariant_violated="transaction_ref_globally_unique",
            detection_method="event_driven", first_divergence_step="order_created",
            root_cause="transaction_ref uses only 8 hex chars of UUID — birthday paradox collision at scale.",
            expected_recovery="Rename one transaction_ref → Update all downstream references → Fix generation to use full UUID",
        ), severity="CRITICAL", tags=["duplicate", "uuid", "collision", "transaction-ref"]),

    FailureScenario(id="F045", category="silent_failure", name="ERP Accepts Request But Returns Stale Data",
        description="ERP reads from a replica with 30s replication lag. Returns old record — integration thinks it failed.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SILENT_FAILURE", invariant_violated="payment_without_erp_order",
            detection_method="scheduled_reconciliation", first_divergence_step="erp_order_created",
            root_cause="ERP GET endpoint reads from read replica with 30s lag. Record created but not yet replicated.",
            expected_recovery="Wait for replication lag → Retry GET → Mark reconciled if record appears",
        ), severity="MEDIUM", tags=["silent", "replication-lag", "erp", "read-replica"]),

    FailureScenario(id="F046", category="infrastructure", name="TLS Certificate Expired on ERP Endpoint",
        description="ERP's TLS cert expired. HTTPS calls fail with SSL handshake error.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="MISSING_STEP", invariant_violated="sla_breach_detection",
            detection_method="event_driven", first_divergence_step="erp_order_created",
            root_cause="ERP TLS certificate expired. All HTTPS connections refused. Auto-renewal failed silently.",
            expected_recovery="Renew certificate → Verify endpoint reachable → Replay queued ERP calls",
        ), severity="CRITICAL", tags=["infrastructure", "tls", "certificate", "ssl"]),

    FailureScenario(id="F047", category="schema_drift", name="Enum Value Added — Unhandled Status",
        description="ERP added a new order status 'ON_HOLD'. Invariant's state machine has no transition for it.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SCHEMA_DRIFT", invariant_violated="all_states_mapped",
            detection_method="event_driven", first_divergence_step="erp_order_created",
            root_cause="ERP v3 added ON_HOLD status for fraud review. Invariant's CHECK constraint rejects it.",
            expected_recovery="Add ON_HOLD to state machine → Define ON_HOLD → IN_PROGRESS transition → Redeploy",
        ), severity="MEDIUM", tags=["schema-drift", "enum", "state-machine"]),

    FailureScenario(id="F048", category="data_mismatch", name="Timezone Bug — IST Stored as UTC",
        description="Order timestamps stored as IST but assumed to be UTC. All time-based SLAs off by 5.5 hours.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="DATA_MISMATCH", invariant_violated="event_timestamps_utc_normalized",
            detection_method="scheduled_reconciliation", first_divergence_step="order_created",
            root_cause="Order service did not set timezone=UTC when creating datetime objects. Stored naive IST datetimes.",
            expected_recovery="Migrate timestamps to UTC → Recalculate SLA deadlines → Update monitoring windows",
        ), severity="HIGH", tags=["data-mismatch", "timezone", "utc", "ist"]),

    FailureScenario(id="F049", category="orphan_record", name="Cancelled Order With Active Shipment",
        description="Order cancelled but shipment not recalled. Goods in transit for cancelled order.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="ORPHAN_RECORD", invariant_violated="no_active_shipment_for_cancelled_order",
            detection_method="event_driven", first_divergence_step="shipment_created",
            root_cause="Cancellation saga did not include a shipping recall step. Shipment compensation not implemented.",
            expected_recovery="Instruct carrier to intercept shipment → Return to warehouse → Initiate refund",
        ), severity="HIGH", tags=["orphan", "cancellation", "shipment", "saga-gap"]),

    FailureScenario(id="F050", category="silent_failure", name="Pub/Sub Message Body Truncated",
        description="Pub/Sub message body exceeds 10MB limit and is silently truncated. JSON is malformed.",
        simulate_params={"failure_mode": "none"},
        ground_truth=GroundTruth(
            incident_type="SILENT_FAILURE", invariant_violated="all_events_normalized",
            detection_method="event_driven", first_divergence_step="erp_order_created",
            root_cause="Large order with 500 line items produces a 12MB event payload exceeding Pub/Sub 10MB limit.",
            expected_recovery="Split large event into chunked events → Update normalizer to handle chunked events",
        ), severity="HIGH", tags=["silent", "pubsub", "payload-size", "large-order"]),
]


def get_scenario(scenario_id: str) -> FailureScenario | None:
    return next((s for s in SCENARIOS if s.id == scenario_id), None)


def get_by_category(category: str) -> list[FailureScenario]:
    return [s for s in SCENARIOS if s.category == category]


def get_by_severity(severity: str) -> list[FailureScenario]:
    return [s for s in SCENARIOS if s.severity == severity]


CATEGORY_SUMMARY = {
    cat: len(get_by_category(cat))
    for cat in {s.category for s in SCENARIOS}
}

SEVERITY_SUMMARY = {
    sev: len(get_by_severity(sev))
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
}

