import structlog
from typing import Optional, Any
from datetime import datetime, timezone
from app.models.icef import CanonicalEvent
from app.models.domain import TransactionState, StepState

logger = structlog.get_logger()

EXPECTED_STEPS_ORDER = [
    "order_created",
    "payment_captured",
    "erp_order_created",
    "inventory_reserved",
    "invoice_generated",
    "shipment_created",
]

EVENT_TO_STEP = {
    "order.created": "order_created",
    "payment.captured": "payment_captured",
    "erp.order_created": "erp_order_created",
    "erp.inventory_reserved": "inventory_reserved",
    "erp.invoice_generated": "invoice_generated",
    "shipment.created": "shipment_created",
}


class TransactionStateMachine:
    def __init__(self):
        # In-memory transaction store: txn_ref -> dict state
        self._transactions: dict[str, dict[str, Any]] = {}

    def get_or_create(self, txn_ref: str) -> dict[str, Any]:
        if txn_ref not in self._transactions:
            self._transactions[txn_ref] = {
                "transaction_ref": txn_ref,
                "state": TransactionState.INITIATED.value,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "steps": {step: {"state": StepState.PENDING.value, "data": None, "event_id": None} for step in EXPECTED_STEPS_ORDER},
                "events": [],
            }
        return self._transactions[txn_ref]

    def get_transaction(self, txn_ref: str) -> Optional[dict[str, Any]]:
        return self._transactions.get(txn_ref)

    def list_transactions(self) -> list[dict[str, Any]]:
        return list(self._transactions.values())

    def apply_event(self, event: CanonicalEvent, txn_ref: str) -> tuple[dict[str, Any], Optional[str]]:
        """
        Transitions the state machine based on the incoming event.
        Returns (transaction_dict, anomaly_or_ordering_violation_error).
        """
        txn = self.get_or_create(txn_ref)
        txn["events"].append(event.model_dump(mode="json"))
        txn["updated_at"] = datetime.now(timezone.utc)

        canonical_type = event.meta.canonical_event_type
        step_key = EVENT_TO_STEP.get(canonical_type)
        ordering_issue = None

        if step_key:
            step = txn["steps"][step_key]
            if step["state"] == StepState.COMPLETED.value:
                # Duplicate step detected
                logger.warning("duplicate_step_event_received", step=step_key, txn_ref=txn_ref)
            else:
                # Check ordering
                step_idx = EXPECTED_STEPS_ORDER.index(step_key)
                for prev_step in EXPECTED_STEPS_ORDER[:step_idx]:
                    if txn["steps"][prev_step]["state"] != StepState.COMPLETED.value:
                        ordering_issue = f"Out of order step: {step_key} completed before {prev_step}"
                        break

                step["state"] = StepState.COMPLETED.value
                step["data"] = event.data
                step["event_id"] = event.meta.event_id

        # Update overall state
        completed_steps = [k for k, v in txn["steps"].items() if v["state"] == StepState.COMPLETED.value]
        if len(completed_steps) == len(EXPECTED_STEPS_ORDER):
            txn["state"] = TransactionState.COMPLETED.value
        elif len(completed_steps) > 0:
            if txn["state"] == TransactionState.INITIATED.value:
                txn["state"] = TransactionState.IN_PROGRESS.value

        return txn, ordering_issue

    def mark_inconsistent(self, txn_ref: str, reason: str):
        txn = self.get_transaction(txn_ref)
        if txn:
            txn["state"] = TransactionState.INCONSISTENT.value
            txn["inconsistent_reason"] = reason

